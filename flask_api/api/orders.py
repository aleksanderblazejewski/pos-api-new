from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


from flask import jsonify, request

from flask_api.api import api_bp
from flask_api.extensions import db
from flask_api.models import (
    Kelnerzy,
    Menu,
    Pracownicy,
    Strefa,
    Stoliki,
    Zamowienia,
    Zam_Poz,
)
from flask_api.utils import bool_from_status, bool_from_wydane, parse_iso_datetime


@api_bp.post("/orders/<int:order_id>/items")
def add_order_item(order_id: int):
    data = request.get_json(silent=True) or {}
    name = data.get("Name")
    qty = int(data.get("Qty", 1))

    if not name or qty <= 0:
        return jsonify({"error": "Missing Name or invalid Qty"}), 400

    zam = Zamowienia.query.get_or_404(order_id)

    menu_row = Menu.query.filter_by(Nazwa=name).first()
    if not menu_row:
        menu_row = Menu(Nazwa=name, Cena=0, Opis="AUTO", Alergeny=None)
        db.session.add(menu_row)
        db.session.flush()

    poz = Zam_Poz(
        Zamowienia_ID=zam.ID,
        Menu_ID=menu_row.ID,
        Ilosc=qty,
        Wydane="N",
    )
    db.session.add(poz)
    db.session.commit()

    return jsonify(
        {
            "ItemId": poz.ID,
            "OrderId": zam.ID,
            "Name": menu_row.Nazwa,
            "Qty": int(poz.Ilosc),
            "IsServed": False,
        }
    ), 201


@api_bp.patch("/orders/<int:order_id>/items/<int:item_id>")
def update_order_item(order_id: int, item_id: int):
    data = request.get_json(silent=True) or {}

    poz = Zam_Poz.query.filter_by(ID=item_id, Zamowienia_ID=order_id).first()
    if not poz:
        return jsonify({"error": "Item not found"}), 404

    if "Qty" in data:
        qty = int(data["Qty"])
        if qty <= 0:
            return jsonify({"error": "Qty must be > 0"}), 400
        poz.Ilosc = qty

    if "Served" in data:
        poz.Wydane = "Y" if bool(data["Served"]) else "N"

    db.session.commit()
    return jsonify({"status": "ok"})


@api_bp.delete("/orders/<int:order_id>/items/<int:item_id>")
def delete_order_item(order_id: int, item_id: int):
    poz = Zam_Poz.query.filter_by(ID=item_id, Zamowienia_ID=order_id).first()
    if not poz:
        return jsonify({"error": "Item not found"}), 404

    db.session.delete(poz)
    db.session.commit()
    return jsonify({"status": "ok"})


@api_bp.get("/orders")
def get_orders():
    zamowienia = Zamowienia.query.all()
    result_by_table = {}

    for zam in zamowienia:
        pozycje = (
            db.session.query(Zam_Poz, Menu)
            .join(Menu, Menu.ID == Zam_Poz.Menu_ID)
            .filter(Zam_Poz.Zamowienia_ID == zam.ID)
            .all()
        )

        items = []
        any_items = False
        all_served = True

        for poz, menu in pozycje:
            any_items = True
            served = bool_from_wydane(poz.Wydane)
            if not served:
                all_served = False

            items.append(
                {
                    "ItemId": poz.ID,
                    "Name": menu.Nazwa,
                    "Qty": int(poz.Ilosc),
                    "IsServed": served,
                }
            )

        is_served = all_served if any_items else False

        order_json = {
            "OrderId": zam.ID,
            "Items": items,
            "IsServed": is_served,
            "IsSettled": bool_from_status(zam.Status),
            "CreatedAt": zam.Data.isoformat(),
        }

        table_id = zam.Stoliki_ID
        result_by_table.setdefault(table_id, {"TableId": table_id, "Orders": []})
        result_by_table[table_id]["Orders"].append(order_json)

    return jsonify(list(result_by_table.values()))


@api_bp.post("/orders")
def create_order():
    data = request.get_json(silent=True) or {}
    table_id = data.get("TableId")
    waiter_id = data.get("WaiterId")
    items = data.get("Items", [])
    notes = data.get("Notes", "")

    if not table_id or not waiter_id or not items:
        return jsonify({"error": "Missing TableId / WaiterId / Items"}), 400

    now = datetime.now(ZoneInfo("Europe/Warsaw")).replace(tzinfo=None)
    zam = Zamowienia(
        Data=now,
        Status="open",
        Uwagi=notes,
        Kelnerzy_ID=waiter_id,
        Stoliki_ID=table_id,
    )
    db.session.add(zam)
    db.session.flush()

    for it in items:
        menu_id = it.get("MenuId")
        qty = it.get("Qty", 1)
        if not menu_id:
            continue
        db.session.add(
            Zam_Poz(
                Zamowienia_ID=zam.ID,
                Menu_ID=menu_id,
                Ilosc=qty,
                Wydane="N",
            )
        )

    db.session.commit()
    return jsonify({"OrderId": zam.ID}), 201


@api_bp.patch("/orders/<int:order_id>/status")
def update_order_status(order_id: int):
    data = request.get_json(silent=True) or {}
    zam = Zamowienia.query.get_or_404(order_id)

    if "Status" in data:
        zam.Status = data["Status"]

    if data.get("SetAllServed"):
        Zam_Poz.query.filter_by(Zamowienia_ID=order_id).update({"Wydane": "Y"})

    db.session.commit()
    return jsonify({"status": "ok"})


@api_bp.delete("/orders/<int:order_id>")
def delete_order(order_id: int):
    zam = db.session.get(Zamowienia, order_id)
    if not zam:
        return jsonify({"error": "Order not found"}), 404

    Zam_Poz.query.filter_by(Zamowienia_ID=order_id).delete()
    db.session.delete(zam)
    db.session.commit()
    return jsonify({"status": "ok"})


@api_bp.post("/orders/sync")
def sync_orders():
    data = request.get_json(silent=True) or []
    if not isinstance(data, list):
        return jsonify({"error": "Expected a JSON array"}), 400

    def get_default_waiter_id():
        kelner = Kelnerzy.query.first()
        if kelner:
            return kelner.ID

        prac = Pracownicy.query.first()
        if not prac:
            prac = Pracownicy(
                Numer_prac=1,
                Nazwisko="System",
                Imie="System",
                Tel="000000000",
            )
            db.session.add(prac)
            db.session.flush()

        strefa = Strefa.query.first()
        if not strefa:
            strefa = Strefa(Nazwa="Domyślna")
            db.session.add(strefa)
            db.session.flush()

        kelner = Kelnerzy(Pracownicy_ID=prac.ID, Strefa_ID=strefa.ID)
        db.session.add(kelner)
        db.session.flush()
        if kelner.Strefa_ID is None:
            kelner.Strefa_ID = strefa.ID
        if strefa not in kelner.strefy:
            kelner.strefy.append(strefa)
        return kelner.ID

    default_waiter_id = get_default_waiter_id()

    Zam_Poz.query.delete()
    Zamowienia.query.delete()
    db.session.flush()

    orders_count = 0
    positions_count = 0

    for table_block in data:
        table_id = table_block.get("TableId")
        if table_id is None:
            continue

        stolik = Stoliki.query.get(table_id)
        if not stolik:
            strefa = Strefa.query.first()
            if not strefa:
                strefa = Strefa(Nazwa="Domyślna")
                db.session.add(strefa)
                db.session.flush()

            stolik = Stoliki(ID=table_id, Ile_osob=4, Strefa_ID=strefa.ID)
            db.session.add(stolik)
            db.session.flush()
            if stolik.Strefa_ID is None:
                stolik.Strefa_ID = strefa.ID
            if strefa not in stolik.strefy:
                stolik.strefy.append(strefa)

        for o in (table_block.get("Orders") or []):
            created_at = parse_iso_datetime(o.get("CreatedAt"))
            is_settled = bool(o.get("IsSettled", False))
            is_served = bool(o.get("IsServed", False))
            status = "paid" if is_settled else "open"

            zam = Zamowienia(
                Data=created_at,
                Status=status,
                Uwagi=None,
                Kelnerzy_ID=default_waiter_id,
                Stoliki_ID=stolik.ID,
            )
            db.session.add(zam)
            db.session.flush()

            for it in (o.get("Items") or []):
                name = it.get("Name", "")
                qty = it.get("Qty", 1)
                if not name:
                    continue

                menu_row = Menu.query.filter_by(Nazwa=name).first()
                if not menu_row:
                    menu_row = Menu(
                        Nazwa=name,
                        Cena=0,
                        Opis="AUTO z orders.json",
                        Alergeny=None,
                    )
                    db.session.add(menu_row)
                    db.session.flush()

                db.session.add(
                    Zam_Poz(
                        Zamowienia_ID=zam.ID,
                        Menu_ID=menu_row.ID,
                        Ilosc=qty,
                        Wydane="Y" if is_served else "N",
                    )
                )
                positions_count += 1

            orders_count += 1

    db.session.commit()
    return jsonify({"status": "ok", "orders": orders_count, "positions": positions_count})


@api_bp.get("/orders/closed")
def get_closed_orders_for_day():
    """
    Zwraca zamówienia zamknięte z danego dnia w formacie:
    [
      { "TableId": 1, "Orders": [ ... ] },
      { "TableId": 2, "Orders": [ ... ] }
    ]

    Query:
      /orders/closed?date=YYYY-MM-DD
    """
    date_str = request.args.get("date")
    if not date_str:
        date_str = datetime.utcnow().strftime("%Y-%m-%d")

    date_str = date_str.strip()

    # jeśli ktoś poda "2025-01-11 12:35:00" albo "2025-01-11T12:35:00"
    if len(date_str) >= 10:
        date_str = date_str[:10]

    try:
        day_start = datetime.strptime(date_str, "%Y-%m-%d")
        day_end = day_start + timedelta(days=1)
    except ValueError:
        return jsonify({"error": "Invalid date format. Expected YYYY-MM-DD"}), 400

    # CLOSED = Status != "open" (np. "paid"). Jeśli u Ciebie jest inaczej, zmień warunek.
    zamowienia = (
        Zamowienia.query
        .filter(Zamowienia.Data >= day_start)
        .filter(Zamowienia.Data < day_end)
        .filter(Zamowienia.Status != "open")
        .all()
    )

    result_by_table = {}

    for zam in zamowienia:
        pozycje = (
            db.session.query(Zam_Poz, Menu)
            .join(Menu, Menu.ID == Zam_Poz.Menu_ID)
            .filter(Zam_Poz.Zamowienia_ID == zam.ID)
            .all()
        )

        items = []
        any_items = False
        all_served = True

        for poz, menu in pozycje:
            any_items = True
            served = bool_from_wydane(poz.Wydane)
            if not served:
                all_served = False

            items.append(
                {
                    "ItemId": poz.ID,
                    "Name": menu.Nazwa,
                    "Qty": int(poz.Ilosc),
                    "IsServed": served,

                    # ⬇️ Opcjonalnie (Twoje DTO nie ma ceny, ale do raportów się przydaje)
                    "Price": float(menu.Cena) if menu.Cena is not None else 0.0,
                    "LineTotal": float(menu.Cena) * int(poz.Ilosc) if menu.Cena is not None else 0.0,
                }
            )

        is_served = all_served if any_items else False

        order_json = {
            "OrderId": zam.ID,
            "Items": items,
            "IsServed": is_served,
            "IsSettled": bool_from_status(zam.Status),
            "CreatedAt": zam.Data.isoformat(),
            # opcjonalnie:
            "Notes": zam.Uwagi,
            "WaiterId": zam.Kelnerzy_ID,
        }

        table_id = zam.Stoliki_ID
        result_by_table.setdefault(table_id, {"TableId": table_id, "Orders": []})
        result_by_table[table_id]["Orders"].append(order_json)

    return jsonify(list(result_by_table.values()))


@api_bp.post("/orders/closed/purge")
def purge_closed_orders_for_day():
    """
    Usuwa z bazy zamówienia zamknięte z danego dnia (Status != 'open')
    + wszystkie pozycje Zam_Poz powiązane z tymi zamówieniami.

    Query:
      /orders/closed/purge?date=YYYY-MM-DD
    """
    date_str = request.args.get("date")
    if not date_str:
        return jsonify({"error": "Missing ?date=YYYY-MM-DD"}), 400

    date_str = date_str.strip()
    if len(date_str) >= 10:
        date_str = date_str[:10]

    try:
        day_start = datetime.strptime(date_str, "%Y-%m-%d")
        day_end = day_start + timedelta(days=1)
    except ValueError:
        return jsonify({"error": "Invalid date format. Expected YYYY-MM-DD"}), 400

    # znajdź zamówienia "closed"
    zam_ids = [
        z.ID for z in (
            Zamowienia.query
            .filter(Zamowienia.Data >= day_start)
            .filter(Zamowienia.Data < day_end)
            .filter(Zamowienia.Status != "open")
            .all()
        )
    ]

    if not zam_ids:
        return jsonify({"status": "ok", "deleted_orders": 0, "deleted_positions": 0})

    # najpierw pozycje
    deleted_positions = (
        Zam_Poz.query
        .filter(Zam_Poz.Zamowienia_ID.in_(zam_ids))
        .delete(synchronize_session=False)
    )

    # potem zamówienia
    deleted_orders = (
        Zamowienia.query
        .filter(Zamowienia.ID.in_(zam_ids))
        .delete(synchronize_session=False)
    )

    db.session.commit()

    return jsonify({
        "status": "ok",
        "date": date_str,
        "deleted_orders": int(deleted_orders),
        "deleted_positions": int(deleted_positions),
    })
