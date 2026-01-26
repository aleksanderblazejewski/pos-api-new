from datetime import datetime, timedelta

import jwt
from flask import current_app, jsonify, request


def _get_jwt_secret() -> str:
    return current_app.config.get("JWT_SECRET_KEY", "change-me")


def _get_jwt_algorithm() -> str:
    return current_app.config.get("JWT_ALGORITHM", "HS256")


def _get_jwt_exp_seconds() -> int:
    return int(current_app.config.get("JWT_EXPIRES_SECONDS", 3600))


def create_access_token(user_id: int, login: str) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": str(user_id),
        "login": login,
        "iat": now,
        "exp": now + timedelta(seconds=_get_jwt_exp_seconds()),
    }
    token = jwt.encode(payload, _get_jwt_secret(), algorithm=_get_jwt_algorithm())
    if isinstance(token, bytes):
        return token.decode("utf-8")
    return token


def _get_bearer_token() -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        return None
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1]


def require_jwt():
    token = _get_bearer_token()
    if not token:
        return jsonify({"error": "Missing Bearer token"}), 401

    try:
        jwt.decode(token, _get_jwt_secret(), algorithms=[_get_jwt_algorithm()])
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401

    return None
