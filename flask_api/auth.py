import base64
import hashlib
import hmac
import json
import time
from flask import current_app, jsonify, request


def _get_jwt_secret() -> str:
    return current_app.config.get("JWT_SECRET_KEY", "change-me")


def _get_jwt_algorithm() -> str:
    return current_app.config.get("JWT_ALGORITHM", "HS256")


def _get_jwt_exp_seconds() -> int:
    return int(current_app.config.get("JWT_EXPIRES_SECONDS", 3600))


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _jwt_signing_input(header: dict, payload: dict) -> bytes:
    header_json = json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return b".".join((_b64url_encode(header_json).encode("utf-8"), _b64url_encode(payload_json).encode("utf-8")))


def _jwt_sign(signing_input: bytes, secret: str) -> str:
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return _b64url_encode(signature)


def _jwt_decode(token: str, secret: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        raise ValueError("Invalid token")

    header_b64, payload_b64, signature_b64 = parts
    header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
    if header.get("alg") != _get_jwt_algorithm():
        raise ValueError("Invalid token")
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    expected_signature = _jwt_sign(signing_input, secret)

    if not hmac.compare_digest(expected_signature, signature_b64):
        raise ValueError("Invalid token")

    payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    exp = payload.get("exp")
    if exp is not None and int(exp) < int(time.time()):
        raise ValueError("Token expired")

    return payload


def create_access_token(user_id: int, login: str) -> str:
    now = int(time.time())
    payload = {
        "sub": str(user_id),
        "login": login,
        "iat": now,
        "exp": now + _get_jwt_exp_seconds(),
    }
    header = {"alg": _get_jwt_algorithm(), "typ": "JWT"}
    signing_input = _jwt_signing_input(header, payload)
    signature = _jwt_sign(signing_input, _get_jwt_secret())
    return f"{signing_input.decode('utf-8')}.{signature}"


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
        _jwt_decode(token, _get_jwt_secret())
    except ValueError as exc:
        message = str(exc) or "Invalid token"
        return jsonify({"error": message}), 401

    return None
