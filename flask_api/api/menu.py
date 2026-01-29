from flask import jsonify, request

from flask_api.api import api_bp
from flask_api.extensions import db
from flask_api.models import Menu, Zam_Poz


@api_bp.get("/menu")
def get_menu():
    items = Menu.query.all()
    result = []
    for m in items:
        category = m.Typ or "Inne"
        result.append(
            {
                "Id": m.ID,
                "Name": m.Nazwa,
                "Category": category,
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

    incoming_ids = set()
    for item in data:
        menu_id = item.get("Id")
        if menu_id is not None:
            incoming_ids.add(menu_id)

    existing_ids = {row.ID for row in Menu.query.with_entities(Menu.ID).all()}
    removed_ids = existing_ids - incoming_ids
    if removed_ids:
        Zam_Poz.query.filter(Zam_Poz.Menu_ID.in_(removed_ids)).delete(
            synchronize_session=False
        )
        Menu.query.filter(Menu.ID.in_(removed_ids)).delete(
            synchronize_session=False
        )

    for item in data:
        menu_id = item.get("Id")
        if menu_id is None:
            continue

        name = item.get("Name", "")
        price = item.get("Price", 0)
        category = item.get("Category") or item.get("Type") or item.get("Typ")

        menu_row = Menu.query.get(menu_id)
        if menu_row:
            menu_row.Nazwa = name
            menu_row.Typ = category
            menu_row.Cena = price
            if menu_row.Opis is None:
                menu_row.Opis = ""
        else:
            db.session.add(
                Menu(
                    ID=menu_id,
                    Nazwa=name,
                    Typ=category,
                    Cena=price,
                    Opis="",
                    Alergeny=None,
                )
            )

    db.session.commit()
    return jsonify({"status": "ok", "count": len(data)})


@api_bp.delete("/menu/<int:menu_id>")
def delete_menu_item(menu_id: int):
    menu_row = Menu.query.get(menu_id)
    if not menu_row:
        return jsonify({"error": "Menu item not found"}), 404

    Zam_Poz.query.filter_by(Menu_ID=menu_id).delete()
    db.session.delete(menu_row)
    db.session.commit()
    return jsonify({"status": "ok"})
