from flask import jsonify, request

from flask_api.api import api_bp
from flask_api.extensions import db
from flask_api.models import Magazyn


@api_bp.get("/stock")
def get_stock():
    items = Magazyn.query.order_by(Magazyn.Nazwa.asc()).all()
    return jsonify([
        {
            "Id": x.ID,
            "Name": x.Nazwa,
            "Unit": x.Jednostka,
            "Qty": float(x.Ilosc),
        }
        for x in items
    ])


@api_bp.post("/stock")
def create_stock_item():
    data = request.get_json(silent=True) or {}
    name = (data.get("Name") or "").strip()
    unit = (data.get("Unit") or "").strip()

    if not name or not unit:
        return jsonify({"error": "Missing Name or Unit"}), 400

    try:
        qty = float(data.get("Qty", 0))
    except Exception:
        return jsonify({"error": "Invalid Qty"}), 400

    row = Magazyn(Nazwa=name, Jednostka=unit, Ilosc=qty)
    db.session.add(row)
    db.session.commit()
    return jsonify({"Id": row.ID}), 201


@api_bp.patch("/stock/<int:item_id>")
def patch_stock_item(item_id: int):
    data = request.get_json(silent=True) or {}
    row = Magazyn.query.get_or_404(item_id)

    if "Name" in data:
        row.Nazwa = (data.get("Name") or "").strip()

    if "Unit" in data:
        row.Jednostka = (data.get("Unit") or "").strip()

    if "Qty" in data:
        try:
            row.Ilosc = float(data.get("Qty"))
        except Exception:
            return jsonify({"error": "Invalid Qty"}), 400

    db.session.commit()
    return jsonify({"status": "ok"})


@api_bp.post("/stock/<int:item_id>/adjust")
def adjust_stock(item_id: int):
    """
    Body: { "Delta": -2.0, "Reason": "Zużycie" }
    """
    data = request.get_json(silent=True) or {}
    row = Magazyn.query.get_or_404(item_id)

    try:
        delta = float(data.get("Delta", 0))
    except Exception:
        return jsonify({"error": "Invalid Delta"}), 400

    row.Ilosc = float(row.Ilosc) + delta
    db.session.commit()

    return jsonify({"status": "ok", "NewQty": float(row.Ilosc)})
