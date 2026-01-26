from flask import jsonify, request

from flask_api.api import api_bp
from flask_api.extensions import db
from flask_api.models import Strefa, Stoliki, MapaStolikow
from flask_api.utils import DEFAULT_WIDTH, DEFAULT_HEIGHT


# -------------------------
# Helpers
# -------------------------
def _safe_int(value, default: int) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


# -------------------------
# GET /tables
# -------------------------
@api_bp.get("/tables")
def get_tables():
    rows = (
        db.session.query(Stoliki, MapaStolikow)
        .join(MapaStolikow, MapaStolikow.Stoliki_ID == Stoliki.ID)
        .all()
    )

    result = []
    for stolik, mapa in rows:
        level = _safe_int(getattr(mapa, "Poziom", None), 1)

        result.append(
            {
                "Id": stolik.ID,
                "Name": mapa.Nazwa,
                "X": _safe_int(mapa.X_Pos, 0),
                "Y": _safe_int(mapa.Y_Pos, 0),
                "Width": DEFAULT_WIDTH,
                "Height": DEFAULT_HEIGHT,
                "Ile_osob": _safe_int(stolik.Ile_osob, 4),
                "status": "wolny",
                "Level": level,  # zawsze int
            }
        )

    return jsonify(result)


# -------------------------
# POST /tables/sync
# UPSERT mapy + usuwanie brakujących
# -------------------------
@api_bp.post("/tables/sync")
def sync_tables():
    data = request.get_json(silent=True) or []
    if not isinstance(data, list):
        return jsonify({"error": "Expected a JSON array"}), 400

    strefa = Strefa.query.get(1)
    if not strefa:
        strefa = Strefa(ID=1, Nazwa="Sala główna")
        db.session.add(strefa)
        db.session.flush()

    def safe_int(v, default):
        try:
            if v is None:
                return default
            return int(v)
        except Exception:
            return default

    # 1) Grupujemy payload po levelach i kasujemy rekordy mapy,
    #    które NIE występują w payloadzie dla danego levelu.
    #    (uwaga: skoro mamy 1 mapę na stolik, to delete po levelu jest OK)
    levels = {safe_int(it.get("Level", 1), 1) for it in data}
    for lvl in levels:
        ids_for_level = {
            safe_int(it.get("Id"), -1)
            for it in data
            if safe_int(it.get("Level", 1), 1) == lvl and it.get("Id") is not None
        }
        ids_for_level.discard(-1)

        if ids_for_level:
            (MapaStolikow.query
             .filter(MapaStolikow.Poziom == lvl)
             .filter(~MapaStolikow.Stoliki_ID.in_(ids_for_level))
             .delete(synchronize_session=False))
        else:
            (MapaStolikow.query
             .filter(MapaStolikow.Poziom == lvl)
             .delete(synchronize_session=False))

    db.session.flush()

    # 2) UPSERT: aktualizuj istniejący rekord mapy po Stoliki_ID, wstaw tylko gdy brak
    count = 0
    for item in data:
        table_id = item.get("Id")
        if table_id is None:
            continue

        table_id = safe_int(table_id, -1)
        if table_id <= 0:
            continue

        name = (item.get("Name") or "").strip()
        x = safe_int(item.get("X", 0), 0)
        y = safe_int(item.get("Y", 0), 0)
        level = safe_int(item.get("Level", 1), 1)

        stolik = Stoliki.query.get(table_id)
        if not stolik:
            stolik = Stoliki(ID=table_id, Ile_osob=4, Strefa_ID=strefa.ID)
            db.session.add(stolik)
            db.session.flush()
        else:
            if stolik.Strefa_ID is None:
                stolik.Strefa_ID = strefa.ID

        row = MapaStolikow.query.filter_by(Stoliki_ID=stolik.ID).first()
        if row:
            row.X_Pos = x
            row.Y_Pos = y
            row.Rotation = 0
            row.Nazwa = name
            row.Poziom = level
        else:
            db.session.add(MapaStolikow(
                Stoliki_ID=stolik.ID,
                X_Pos=x,
                Y_Pos=y,
                Rotation=0,
                Nazwa=name,
                Poziom=level,
            ))

        count += 1

    db.session.commit()
    return jsonify({"status": "ok", "count": count})



# -------------------------
# PATCH /tables/<id> (Ile_osob)
# -------------------------
@api_bp.patch("/tables/<int:table_id>")
def patch_table(table_id: int):
    data = request.get_json(silent=True) or {}

    if "Ile_osob" not in data:
        return jsonify({"error": "Missing field Ile_osob"}), 400

    people = _safe_int(data.get("Ile_osob"), -1)
    if people < 1 or people > 50:
        return jsonify({"error": "Ile_osob out of range"}), 400

    stolik = Stoliki.query.get(table_id)
    if not stolik:
        return jsonify({"error": "Table not found"}), 404

    stolik.Ile_osob = people
    db.session.commit()

    return jsonify({"status": "ok", "Id": stolik.ID, "Ile_osob": stolik.Ile_osob}), 200
