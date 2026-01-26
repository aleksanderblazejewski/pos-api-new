from flask import jsonify, request

from flask_api.api import api_bp
from flask_api.extensions import db
from flask_api.models import (
    Strefa,
    Stoliki,
    Kelnerzy,
    Pracownicy,
    StolikiStrefy,     # <-- model tabeli łączącej
    KelnerzyStrefy,    # <-- model tabeli łączącej
)


DEFAULT_GROUP_ID = 1


def _ensure_default_zone():
    default_zone = Strefa.query.get(DEFAULT_GROUP_ID)
    if not default_zone:
        default_zone = Strefa(ID=DEFAULT_GROUP_ID, Nazwa="Sala główna")
        db.session.add(default_zone)
        db.session.flush()
    return default_zone


@api_bp.get("/table-groups")
def get_table_groups():
    """
    Kompatybilnie jak wcześniej:
    - AssignedTableIds: lista ID stolików w strefie
    - AssignedStaffIds: lista Pracownicy_ID kelnerów w strefie
    Czytamy z tabel łączących (many-to-many).
    """
    strefy = Strefa.query.all()
    result = []

    for strefa in strefy:
        # stoliki przypisane do strefy
        table_links = StolikiStrefy.query.filter_by(Strefa_ID=strefa.ID).all()
        table_ids = [x.Stoliki_ID for x in table_links]

        # kelnerzy przypisani do strefy (zwracamy Pracownicy_ID jak wcześniej)
        waiter_links = KelnerzyStrefy.query.filter_by(Strefa_ID=strefa.ID).all()
        kelner_ids = [x.Kelnerzy_ID for x in waiter_links]

        if kelner_ids:
            kelnerzy = Kelnerzy.query.filter(Kelnerzy.ID.in_(kelner_ids)).all()
            staff_ids = [k.Pracownicy_ID for k in kelnerzy]
        else:
            staff_ids = []

        result.append(
            {
                "Id": strefa.ID,
                "Name": strefa.Nazwa,
                "AssignedTableIds": table_ids,
                "AssignedStaffIds": staff_ids,
            }
        )

    return jsonify(result)


@api_bp.post("/table-groups/sync")
def sync_table_groups():
    """
    Kompatybilnie jak wcześniej:
    payload: [{Id, Name, AssignedTableIds, AssignedStaffIds}, ...]

    Nowe zachowanie:
    - replace relacji w tabelach łączących
    - utrzymanie legacy: Stoliki.Strefa_ID i Kelnerzy.Strefa_ID jako "primary zone"
      (pierwsza strefa z payloadu dla danego obiektu, a jeśli brak -> DEFAULT_GROUP_ID)
    """
    data = request.get_json(silent=True) or []
    if not isinstance(data, list):
        return jsonify({"error": "Expected a JSON array"}), 400

    _ensure_default_zone()

    # 1) upsert stref
    zone_ids = []
    for item in data:
        gid = item.get("Id")
        name = item.get("Name", "")
        if gid is None:
            continue
        gid = int(gid)
        zone_ids.append(gid)

        strefa = Strefa.query.get(gid)
        if not strefa:
            db.session.add(Strefa(ID=gid, Nazwa=name))
        else:
            strefa.Nazwa = name

    db.session.flush()

    # 2) Zbuduj mapy z payloadu:
    #    zone -> tables/staff
    zone_to_tables: dict[int, set[int]] = {}
    zone_to_staff: dict[int, set[int]] = {}

    # oraz "primary zone" dla legacy kolumn:
    table_primary_zone: dict[int, int] = {}
    staff_primary_zone: dict[int, int] = {}

    for item in data:
        gid = item.get("Id")
        if gid is None:
            continue
        gid = int(gid)

        tset = zone_to_tables.setdefault(gid, set())
        for tid in (item.get("AssignedTableIds") or []):
            tid = int(tid)
            tset.add(tid)
            # jeśli stolik ma trafić do kilku stref, "primary" ustawiamy jako pierwszą napotkaną
            table_primary_zone.setdefault(tid, gid)

        sset = zone_to_staff.setdefault(gid, set())
        for sid in (item.get("AssignedStaffIds") or []):
            sid = int(sid)
            sset.add(sid)
            staff_primary_zone.setdefault(sid, gid)

    # 3) REPLACE relacji stolik-strefa w tabeli łączącej (per strefa)
    #    Czyścimy tylko strefy, które przyszły w payloadzie (nie ruszamy innych, jeśli istnieją dodatkowo)
    if zone_ids:
        StolikiStrefy.query.filter(StolikiStrefy.Strefa_ID.in_(zone_ids)).delete(synchronize_session=False)
        db.session.flush()

    # Wstaw nowe relacje
    for gid, tids in zone_to_tables.items():
        for tid in tids:
            # jeśli stolik nie istnieje w Stoliki, to go utwórz (żeby przypisanie działało)
            st = Stoliki.query.get(tid)
            if not st:
                st = Stoliki(ID=tid, Ile_osob=4, Strefa_ID=DEFAULT_GROUP_ID)
                db.session.add(st)
                db.session.flush()

            db.session.add(StolikiStrefy(Stoliki_ID=tid, Strefa_ID=gid))

    db.session.flush()

    # 4) REPLACE relacji kelner-strefa (per strefa)
    if zone_ids:
        KelnerzyStrefy.query.filter(KelnerzyStrefy.Strefa_ID.in_(zone_ids)).delete(synchronize_session=False)
        db.session.flush()

    # Musimy mapować AssignedStaffIds (Pracownicy.ID) -> Kelnerzy.ID
    payload_staff_ids = set()
    for sids in zone_to_staff.values():
        payload_staff_ids |= sids

    staff_to_kelner_id: dict[int, int] = {}
    if payload_staff_ids:
        # zapewnij, że pracownik istnieje
        existing_workers = {p.ID for p in Pracownicy.query.filter(Pracownicy.ID.in_(list(payload_staff_ids))).all()}

        # pobierz istniejące Kelnerzy dla pracowników
        existing_kelnerzy = Kelnerzy.query.filter(Kelnerzy.Pracownicy_ID.in_(list(payload_staff_ids))).all()
        for k in existing_kelnerzy:
            staff_to_kelner_id[k.Pracownicy_ID] = k.ID

        # utwórz brakujących kelnerów dla istniejących pracowników
        for sid in payload_staff_ids:
            if sid not in existing_workers:
                # jeśli UI wysłał ID którego nie ma w Pracownicy, pomijamy (żeby nie robić 500)
                continue
            if sid not in staff_to_kelner_id:
                new_k = Kelnerzy(Pracownicy_ID=sid, Strefa_ID=DEFAULT_GROUP_ID)
                db.session.add(new_k)
                db.session.flush()
                staff_to_kelner_id[sid] = new_k.ID

    # Wstaw relacje kelner-strefa
    for gid, sids in zone_to_staff.items():
        for sid in sids:
            kelner_id = staff_to_kelner_id.get(sid)
            if not kelner_id:
                continue
            db.session.add(KelnerzyStrefy(Kelnerzy_ID=kelner_id, Strefa_ID=gid))

    db.session.flush()

    # 5) LEGACY: ustaw "primary strefę" w Stoliki.Strefa_ID i Kelnerzy.Strefa_ID
    #    (żeby stare endpointy / logika nadal działały)
    # Stoliki
    all_tables = Stoliki.query.all()
    for t in all_tables:
        t.Strefa_ID = table_primary_zone.get(t.ID, DEFAULT_GROUP_ID)

    # Kelnerzy – po Pracownicy_ID
    all_waiters = Kelnerzy.query.all()
    for k in all_waiters:
        k.Strefa_ID = staff_primary_zone.get(k.Pracownicy_ID, DEFAULT_GROUP_ID)

    db.session.commit()
    return jsonify({"status": "ok", "groups": len(data)})
