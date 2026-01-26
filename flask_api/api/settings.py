import os
from flask import jsonify, request

from flask_api.api import api_bp
from flask_api.extensions import db
from flask_api.models import Ustawienia


def _get(name: str) -> Ustawienia | None:
    return Ustawienia.query.filter_by(Nazwa_opcji=name).first()


def _get_value(name: str, default: str | None = None) -> str | None:
    row = _get(name)
    if not row:
        return default
    return row.Wartosc


def _set_value(name: str, value: str, typ: str | None = None, opis: str | None = None):
    row = _get(name)
    if not row:
        row = Ustawienia(Nazwa_opcji=name, Wartosc=str(value), Typ=typ, Opis=opis)
        db.session.add(row)
    else:
        row.Wartosc = str(value)
        if typ is not None:
            row.Typ = typ
        if opis is not None:
            row.Opis = opis


def _to_bool(v: str | None) -> bool:
    if v is None:
        return False
    return str(v).strip().lower() in ("1", "true", "yes", "y", "tak")


def _to_int(v: str | None, default: int = 0) -> int:
    try:
        return int(str(v).strip())
    except:
        return default


# ---------- PUBLIC API ----------

@api_bp.get("/settings")
def get_settings_all():
    items = Ustawienia.query.order_by(Ustawienia.ID).all()
    return jsonify([
        {
            "Id": s.ID,
            "Name": s.Nazwa_opcji,
            "Value": s.Wartosc,
            "Type": s.Typ,
            "Description": s.Opis
        } for s in items
    ])


@api_bp.get("/settings/reservations")
def get_reservation_settings():
    """
    Zwraca ustawienia rezerwacji w formie wygodnej dla UI.
    Źródłem jest tabela Ustawienia (key/value).
    """
    return jsonify({
        "RequireApproval": _to_bool(_get_value("Zatwierdzanie_Rezerwacji", "0")),
        "ReservationIntervalMinutes": _to_int(_get_value("Odstep_miedzy_rezerwacjami", "0"), 0),
        "OpenFrom": _get_value("godziny_otwarcia_od", ""),
        "CloseTo": _get_value("godziny_zamkniecia_od", ""),
    })


@api_bp.put("/settings/reservations")
def put_reservation_settings():
    """
    Body JSON:
    {
      "RequireApproval": true/false,
      "ReservationIntervalMinutes": 15,
      "OpenFrom": "10:00",
      "CloseTo": "22:00"
    }
    """
    payload = request.get_json(silent=True) or {}

    if "RequireApproval" in payload:
        _set_value("Zatwierdzanie_Rezerwacji", "1" if bool(payload["RequireApproval"]) else "0", typ="bool",
                   opis="0 - nie potrzeba, 1 - potrzeba")

    if "ReservationIntervalMinutes" in payload:
        _set_value("Odstep_miedzy_rezerwacjami", str(int(payload["ReservationIntervalMinutes"])), typ="int",
                   opis="Odstęp między rezerwacjami w minutach")

    if "OpenFrom" in payload:
        _set_value("godziny_otwarcia_od", str(payload["OpenFrom"]).strip(), typ="time",
                   opis="Godzina otwarcia (HH:MM)")

    if "CloseTo" in payload:
        _set_value("godziny_zamkniecia_od", str(payload["CloseTo"]).strip(), typ="time",
                   opis="Godzina zamknięcia (HH:MM)")

    db.session.commit()
    return jsonify({"status": "ok"})


@api_bp.patch("/settings/bulk")
def patch_settings_bulk():
    """
    Body JSON (obiekt key->value), np.:
    {
      "Zatwierdzanie_Rezerwacji": "1",
      "Odstep_miedzy_rezerwacjami": "15",
      "godziny_otwarcia_od": "10:00",
      "godziny_zamkniecia_od": "22:00"
    }
    """
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "Expected JSON object"}), 400

    for k, v in payload.items():
        _set_value(k, str(v))

    db.session.commit()
    return jsonify({"status": "ok"})


@api_bp.get("/settings/admin")
def get_admin_settings():
    admin_login = os.getenv("ADMIN_LOGIN", "admin")
    admin_password = os.getenv("ADMIN_PASSWORD", "admin")
    return jsonify({"AdminLogin": admin_login, "AdminPassword": admin_password})
