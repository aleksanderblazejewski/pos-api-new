from flask import jsonify, request

from flask_api.api import api_bp
from flask_api.extensions import db
from flask_api.models import Menu, Zam_Poz


@api_bp.get("/menu")
def get_menu():
    items = Menu.query.all()
    result = []
    for m in items:
        result.append(
            {
                "Id": m.ID,
                "Name": m.Nazwa,
                "Category": "Inne",
                "Price": float(m.Cena),
                "IsActive": True,
            }
        )
    return jsonify(result)


@api_bp.post("/menu/sync")
def sync_menu():
    data = request.get_json(silent=True) or []
    if not isinstance(data, list):
        return jsonify({"error": "Expected a JSON array"}), 400

    Zam_Poz.query.delete()
    Menu.query.delete()
    db.session.flush()

    for item in data:
        menu_id = item.get("Id")
        if menu_id is None:
            continue

        name = item.get("Name", "")
        price = item.get("Price", 0)

        db.session.add(
            Menu(
                ID=menu_id,
                Nazwa=name,
                Cena=price,
                Opis="",
                Alergeny=None,
            )
        )

    db.session.commit()
    return jsonify({"status": "ok", "count": len(data)})
