from flask import jsonify, request

from flask_api.api import api_bp
from flask_api.extensions import db
from flask_api.models import Pracownicy, Logowanie, Kelnerzy, Zamowienia


@api_bp.get("/staff")
def get_staff():
    rows = (
        db.session.query(Pracownicy, Logowanie)
        .join(Logowanie, Logowanie.Pracownicy_ID == Pracownicy.ID)
        .all()
    )

    result = []
    for prac, log in rows:
        result.append(
            {
                "Id": prac.ID,
                "FirstName": prac.Imie,
                "LastName": prac.Nazwisko,
                "Phone": prac.Tel,
                "Email": None,
                "Login": log.Login,
                "PasswordHash": log.Haslo,
                "IsActive": True,
            }
        )
    return jsonify(result)


@api_bp.post("/staff")
def create_staff():
    data = request.get_json(silent=True) or {}
    first = data.get("FirstName")
    last = data.get("LastName")
    phone = data.get("Phone")
    login = data.get("Login")
    pwd_hash = data.get("PasswordHash")

    if not all([first, last, phone, login, pwd_hash]):
        return jsonify({"error": "Missing fields"}), 400

    max_num = db.session.query(db.func.max(Pracownicy.Numer_prac)).scalar() or 0
    prac = Pracownicy(
        Numer_prac=max_num + 1,
        Nazwisko=last,
        Imie=first,
        Tel=phone,
    )
    db.session.add(prac)
    db.session.flush()

    log = Logowanie(
        Pracownicy_ID=prac.ID,
        Login=login,
        Haslo=pwd_hash,
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({"Id": prac.ID}), 201


@api_bp.put("/staff/<int:staff_id>")
def update_staff(staff_id: int):
    data = request.get_json(silent=True) or {}
    prac = Pracownicy.query.get_or_404(staff_id)
    log = Logowanie.query.filter_by(Pracownicy_ID=staff_id).first()

    if "FirstName" in data:
        prac.Imie = data["FirstName"]
    if "LastName" in data:
        prac.Nazwisko = data["LastName"]
    if "Phone" in data:
        prac.Tel = data["Phone"]
    if "Login" in data and log:
        log.Login = data["Login"]
    if "PasswordHash" in data and log:
        log.Haslo = data["PasswordHash"]

    db.session.commit()
    return jsonify({"status": "ok"})


@api_bp.delete("/staff/<int:staff_id>")
def delete_staff(staff_id: int):
    prac = Pracownicy.query.get(staff_id)
    if not prac:
        return jsonify({"error": "Staff not found"}), 404

    kelner = Kelnerzy.query.filter_by(Pracownicy_ID=staff_id).first()
    if kelner:
        has_orders = Zamowienia.query.filter_by(Kelnerzy_ID=kelner.ID).first()
        if has_orders:
            return jsonify(
                {
                    "error": "Cannot delete staff with existing orders",
                    "code": "HAS_ORDERS",
                }
            ), 409
        db.session.delete(kelner)

    log = Logowanie.query.filter_by(Pracownicy_ID=staff_id).first()
    if log:
        db.session.delete(log)

    db.session.delete(prac)
    db.session.commit()
    return jsonify({"status": "ok"})


@api_bp.post("/staff/sync")
def sync_staff():
    data = request.get_json(silent=True) or []
    if not isinstance(data, list):
        return jsonify({"error": "Expected a JSON array"}), 400

    seen_ids = set()
    count_new = 0
    count_updated = 0

    for item in data:
        staff_id = item.get("Id")
        if staff_id is None:
            continue

        seen_ids.add(staff_id)

        first = item.get("FirstName", "")
        last = item.get("LastName", "")
        phone = item.get("Phone", "")
        login = item.get("Login", "")
        pwd_hash = item.get("PasswordHash", "")

        prac = Pracownicy.query.get(staff_id)
        if not prac:
            prac = Pracownicy(
                ID=staff_id,
                Numer_prac=staff_id,
                Nazwisko=last,
                Imie=first,
                Tel=phone,
            )
            db.session.add(prac)
            count_new += 1
        else:
            prac.Nazwisko = last
            prac.Imie = first
            prac.Tel = phone
            count_updated += 1

        log = Logowanie.query.filter_by(Pracownicy_ID=prac.ID).first()
        if not log:
            log = Logowanie(
                Pracownicy_ID=prac.ID,
                Login=login,
                Haslo=pwd_hash,
            )
            db.session.add(log)
        else:
            log.Login = login
            log.Haslo = pwd_hash

    db.session.commit()

    return jsonify(
        {
            "status": "ok",
            "new": count_new,
            "updated": count_updated,
            "total_from_json": len(seen_ids),
        }
    )


@api_bp.patch("/staff/<int:staff_id>/password")
def change_password(staff_id: int):
    data = request.get_json(silent=True) or {}
    old_hash = data.get("OldPasswordHash")
    new_hash = data.get("NewPasswordHash")

    if not old_hash or not new_hash:
        return jsonify({"error": "Missing OldPasswordHash / NewPasswordHash"}), 400

    log = Logowanie.query.filter_by(Pracownicy_ID=staff_id).first()
    if not log:
        return jsonify({"error": "User not found"}), 404

    if log.Haslo != old_hash:
        return jsonify({"error": "Invalid old password"}), 403

    log.Haslo = new_hash
    db.session.commit()
    return jsonify({"status": "ok"})
