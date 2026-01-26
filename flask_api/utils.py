from datetime import datetime

DEFAULT_WIDTH = 80
DEFAULT_HEIGHT = 160


def bool_from_status(status: str) -> bool:
    if not status:
        return False
    s = status.strip().lower()
    return s in ("paid", "settled", "closed", "zapłacone", "zamknięte")


def bool_from_wydane(flag: str) -> bool:
    if not flag:
        return False
    return str(flag).upper() in ("Y", "T", "1")


def parse_iso_datetime(value):
    if not value:
        return datetime.utcnow()
    try:
        s = str(value)
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.utcnow()
