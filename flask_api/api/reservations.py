from datetime import datetime, date, time
from flask import jsonify, request

from flask_api.api import api_bp
from flask_api.extensions import db
from flask_api.models import Rezerwacje


def _parse_date(val) -> date | None:
    """
    Akceptuje:
    - "2026-01-14"
    - "14.01.2026"
    - datetime/date
    """
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    s = str(val).strip()
    if not s:
        return None

    # ISO
    if "-" in s:
        return datetime.fromisoformat(s).date()

    # PL dd.mm.yyyy
    if "." in s:
        return datetime.strptime(s, "%d.%m.%Y").date()

    return None


def _parse_time(val) -> time | None:
    """
    Akceptuje:
    - "18:30"
    - "18:30:00"
    - datetime/time
    """
    if val is None:
        return None
    if isinstance(val, time) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.time()

    s = str(val).strip()
    if not s:
        return None

    # "HH:MM" -> dołóż sekundy
    if len(s) == 5:
        s = s + ":00"

    return datetime.strptime(s, "%H:%M:%S").time()


@api_bp.get("/reservations")
def get_reservations():
    items = Rezerwacje.query.all()

    result = []
    for r in items:
        # Składamy “StartTime” na potrzeby UI z Data + Godzina
        start_dt = None
        if r.Data and r.Godzina:
            start_dt = datetime.combine(r.Data, r.Godzina)

        result.append({
            "Id": r.ID,
            "FirstName": r.Imie,
            "LastName": r.Nazwisko,
            "Phone": r.Tel,
            "PeopleCount": r.Ilosc_osob,
            "Date": r.Data.isoformat() if r.Data else None,
            "Time": r.Godzina.strftime("%H:%M:%S") if r.Godzina else None,
            "StartTime": start_dt.isoformat() if start_dt else None,
            "Approved": bool(r.Zatwierdzone),
            "TableId": r.Stoliki_ID
        })

    return jsonify(result)


@api_bp.post("/reservations/sync")
def sync_reservations():
    """
    Tak samo jak w menu.py: przyjmujemy listę i nadpisujemy tabelę.
    JSON: [{ Id, FirstName, LastName, Phone, PeopleCount, Date, Time, Approved, TableId }, ...]
    """
    data = request.get_json(silent=True) or []
    if not isinstance(data, list):
        return jsonify({"error": "Expected a JSON array"}), 400

    Rezerwacje.query.delete()
    db.session.flush()

    count = 0
    for item in data:
        rid = item.get("Id")
        if rid is None:
            continue

        imie = (item.get("FirstName") or "").strip()
        nazwisko = (item.get("LastName") or "").strip()

        # minimum sensu
        if not imie:
            imie = "—"
        if not nazwisko:
            nazwisko = "—"

        d = _parse_date(item.get("Date"))
        t = _parse_time(item.get("Time"))

        # fallback: jeśli UI wyśle StartTime, rozbij to na Data/Godzina
        if (d is None or t is None) and item.get("StartTime"):
            try:
                dt = datetime.fromisoformat(str(item["StartTime"]).replace(" ", "T"))
                d = d or dt.date()
                t = t or dt.time().replace(microsecond=0)
            except:
                pass

        # jeśli nadal brak, to odrzuć rekord (w bazie nullable=False)
        if d is None or t is None:
            continue

        db.session.add(Rezerwacje(
            ID=rid,
            Imie=imie,
            Nazwisko=nazwisko,
            Tel=item.get("Phone"),
            Ilosc_osob=int(item.get("PeopleCount") or 0),
            Data=d,
            Godzina=t,
            Zatwierdzone=bool(item.get("Approved")),
            Stoliki_ID=item.get("TableId")
        ))
        count += 1

    db.session.commit()
    return jsonify({"status": "ok", "count": count})


@api_bp.patch("/reservations/<int:rid>/approved")
def patch_reservation_approved(rid: int):
    """
    Ustawia Zatwierdzone dla rezerwacji.
    Body: { "Approved": true/false }
    """
    payload = request.get_json(silent=True) or {}

    if "Approved" not in payload:
        return jsonify({"error": "Missing field 'Approved' (bool)"}), 400

    approved_val = payload["Approved"]

    # normalizacja do bool (na wypadek 1/0 albo "true"/"false")
    if isinstance(approved_val, bool):
        approved = approved_val
    elif isinstance(approved_val, (int, float)):
        approved = bool(approved_val)
    elif isinstance(approved_val, str):
        approved = approved_val.strip().lower() in ("1", "true", "yes", "y", "tak")
    else:
        return jsonify({"error": "Field 'Approved' must be boolean"}), 400

    r = Rezerwacje.query.filter_by(ID=rid).first()
    if not r:
        return jsonify({"error": f"Reservation {rid} not found"}), 404

    r.Zatwierdzone = approved
    db.session.commit()

    return jsonify({"status": "ok", "Id": rid, "Approved": bool(r.Zatwierdzone)})