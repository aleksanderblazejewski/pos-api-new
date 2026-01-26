import hashlib

from flask import jsonify, request
from flask_api.api import api_bp
from flask_api.auth import create_access_token
from flask_api.models import Logowanie, Pracownicy, db

@api_bp.post("/login")
def login():
    # Pobieramy dane (z obsługa kluczy 'login' lub 'Login')
    data = request.get_json(silent=True) or {}
    login_value = data.get("login") or data.get("Login")
    password_value = (
        data.get("PasswordHash")
        or data.get("password_hash")
        or data.get("password")
        or data.get("Password")
        or data.get("Haslo")
    )

    if not login_value:
        return jsonify({"ok": False, "error": "Brak loginu"}), 400
    if not password_value:
        return jsonify({"ok": False, "error": "Brak hasla"}), 400

    # Szukamy użytkownika
    log = Logowanie.query.filter_by(Login=login_value).first()
    if not log:
        return jsonify({"ok": False, "error": "Nieprawidłowy login"}), 404
    password_sha256 = hashlib.sha256(str(password_value).encode("utf-8")).hexdigest()
    if log.Haslo not in (str(password_value), password_sha256):
        return jsonify({"ok": False, "error": "Nieprawidlowe haslo"}), 403

    # Pobieramy dane pracownika
    personel = Pracownicy.query.get(log.Pracownicy_ID)
    
    token = create_access_token(log.Pracownicy_ID, log.Login)

    # Zwracamy komplet danych do weryfikacji lokalnej i zapisu sesji
    return jsonify({
        "ok": True,
        "id": log.Pracownicy_ID,
        "login": log.Login,
        "imie": personel.Imie if personel else "Nieznany",
        "nazwisko": personel.Nazwisko if personel else "",
        "hash": log.Haslo,  # Przesyłamy hash z bazy
        "token": token,
    }), 200
