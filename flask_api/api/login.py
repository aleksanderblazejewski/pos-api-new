from flask import jsonify, request
from flask_api.api import api_bp
from flask_api.models import Logowanie, Pracownicy, db

@api_bp.post("/login")
def login():
    # Pobieramy dane (z obsługa kluczy 'login' lub 'Login')
    data = request.get_json(silent=True) or {}
    login_value = data.get("login") or data.get("Login")

    if not login_value:
        return jsonify({"ok": False, "error": "Brak loginu"}), 400

    # Szukamy użytkownika
    log = Logowanie.query.filter_by(Login=login_value).first()
    if not log:
        return jsonify({"ok": False, "error": "Nieprawidłowy login"}), 404

    # Pobieramy dane pracownika
    personel = Pracownicy.query.get(log.Pracownicy_ID)
    
    # Zwracamy komplet danych do weryfikacji lokalnej i zapisu sesji
    return jsonify({
        "ok": True,
        "id": log.Pracownicy_ID,
        "login": log.Login,
        "imie": personel.Imie if personel else "Nieznany",
        "nazwisko": personel.Nazwisko if personel else "",
        "hash": log.Haslo,  # Przesyłamy hash z bazy
    }), 200