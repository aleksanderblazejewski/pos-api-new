import io
import json
import gzip
import os
from datetime import datetime, date
from pathlib import Path
from contextlib import contextmanager

from flask import jsonify, request, send_file, current_app

from flask_api.api import api_bp


# ======================================================================
# Konfiguracja
# ======================================================================

# Folder na archiwum (zgodnie z Twoim wymaganiem)
RAPORTS_DIR = Path("raports")

# Maksymalny rozmiar body (w bajtach) – zabezpieczenie (domyślnie 10 MB)
DEFAULT_MAX_UPLOAD_BYTES = 50 * 1024 * 1024


# ======================================================================
# Utils: daty, ścieżki
# ======================================================================

def _utc_now_z() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _parse_report_date(value: str) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except Exception:
        raise ValueError("Invalid date format. Expected YYYY-MM-DD")


def _report_path(d: date) -> Path:
    year = f"{d.year:04d}"
    month = f"{d.month:02d}"
    folder = RAPORTS_DIR / year / month
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{d.isoformat()}.json.gz"


def _ensure_report_shape(d: date, obj: dict) -> dict:
    """
    Upewnia się, że raport ma format:
    { "Date": "YYYY-MM-DD", "Entries": [ ... ] }
    """
    if not isinstance(obj, dict):
        obj = {}
    if obj.get("Date") != d.isoformat():
        obj["Date"] = d.isoformat()
    entries = obj.get("Entries")
    if not isinstance(entries, list):
        obj["Entries"] = []
    return obj


# ======================================================================
# Utils: rozmiar uploadu
# ======================================================================

def _max_upload_bytes() -> int:
    # Możesz to nadpisać w configu Flask: app.config["REPORTS_MAX_UPLOAD_BYTES"]
    return int(current_app.config.get("REPORTS_MAX_UPLOAD_BYTES", DEFAULT_MAX_UPLOAD_BYTES))


def _require_body_size_ok(raw: bytes) -> tuple[bool, tuple]:
    limit = _max_upload_bytes()
    if raw is None:
        return False, (jsonify({"error": "Empty body"}), 400)
    if len(raw) == 0:
        return False, (jsonify({"error": "Empty body"}), 400)
    if len(raw) > limit:
        return False, (jsonify({"error": f"Body too large. Limit={limit} bytes"}), 413)
    return True, ()


# ======================================================================
# Utils: lock (Unix fcntl) + atomic save
# ======================================================================

@contextmanager
def _file_lock(lock_path: Path):
    """
    Prosty lock plikowy. Na Linux/Unix używa fcntl.
    Na Windows (i gdy fcntl niedostępne) robi fallback bez OS-locka,
    ale nadal zapis jest atomowy (tmp + rename).
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    f = open(lock_path, "a+", encoding="utf-8")
    try:
        try:
            import fcntl  # Unix only
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        except Exception:
            # Brak twardego locka – fallback
            pass
        yield
    finally:
        try:
            try:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except Exception:
                pass
        finally:
            f.close()


def _load_gz_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def _atomic_save_gz_json(path: Path, obj: dict) -> None:
    """
    Zapis atomowy: zapis do tmp, fsync, potem rename.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")

    with gzip.open(tmp_path, "wt", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

    # Upewnij się, że dane są na dysku (best-effort)
    try:
        with open(tmp_path, "rb") as rf:
            os.fsync(rf.fileno())
    except Exception:
        pass

    tmp_path.replace(path)


# ======================================================================
# Merge / normalizacja wejścia
# ======================================================================

def _entry_from_archive_body(body: dict, d: date) -> dict:
    """
    Tworzy pojedynczy wpis dopisywany do Entries[] dla endpointu /archive.
    """
    return {
        "ReceivedAt": _utc_now_z(),
        "Date": d.isoformat(),
        "Source": body.get("Source"),
        "Payload": body.get("Payload"),
    }


def _entries_from_uploaded_report(report_obj: dict) -> list:
    """
    Dla uploadu json.gz:
    - jeśli report_obj ma Entries[] -> zwraca tę listę
    - jeśli nie -> traktuje całość jako 1 wpis (Entry)
    """
    if isinstance(report_obj, dict) and isinstance(report_obj.get("Entries"), list):
        return report_obj["Entries"]

    # fallback: jedna paczka jako entry
    return [{
        "ReceivedAt": _utc_now_z(),
        "Source": report_obj.get("Source") if isinstance(report_obj, dict) else None,
        "Payload": report_obj.get("Payload") if isinstance(report_obj, dict) else report_obj,
    }]


def _merge_entries(existing_report: dict, d: date, new_entries: list) -> dict:
    existing_report = _ensure_report_shape(d, existing_report)

    if not isinstance(new_entries, list):
        raise ValueError("Entries must be an array")

    # możesz tu dołożyć walidację schematu każdego entry, jeśli chcesz
    existing_report["Entries"].extend(new_entries)
    return existing_report


# ======================================================================
# Endpointy
# ======================================================================

@api_bp.post("/raports/archive")
def reports_archive_json():
    """
    Archiwizacja JSON (nieskompresowany request).
    Body:
      {
        "Date": "YYYY-MM-DD" (opcjonalne; jak brak -> dzisiejsza data serwera),
        "Source": "POS|Waiter|...",
        "Payload": {...}  # dowolne
      }
    Zapis: dopisanie wpisu do Entries[] w YYYY-MM-DD.json.gz
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": "Expected JSON object"}), 400

    date_str = body.get("Date")
    try:
        d = _parse_report_date(date_str) if date_str else date.today()
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    path = _report_path(d)
    lock_path = path.with_suffix(path.suffix + ".lock")

    entry = _entry_from_archive_body(body, d)

    with _file_lock(lock_path):
        existing = _load_gz_json(path) if path.exists() else {}
        merged = _merge_entries(existing, d, [entry])
        _atomic_save_gz_json(path, merged)

    return jsonify({
        "status": "ok",
        "date": d.isoformat(),
        "entries_added": 1,
        "total_entries": len(merged["Entries"]),
        "file": str(path),
    })


@api_bp.post("/raports/upload-gz")
def reports_upload_gz():
    """
    Upload gotowego json.gz (oszczędność transferu).
    Request:
      Content-Type: application/gzip (zalecane)
      Body: gzip(JSON)
    JSON po rozpakowaniu powinien zawierać:
      - Date: "YYYY-MM-DD"
      - Entries: [ ... ]  (zalecane)
    Jeśli nie ma Entries[] -> traktujemy całość jako 1 wpis.
    """
    raw = request.data
    ok, resp = _require_body_size_ok(raw)
    if not ok:
        return resp

    try:
        decompressed = gzip.decompress(raw)
        report_obj = json.loads(decompressed.decode("utf-8"))
    except Exception:
        return jsonify({"error": "Invalid gzip or JSON"}), 400

    if not isinstance(report_obj, dict):
        return jsonify({"error": "Decoded report must be a JSON object"}), 400

    date_str = report_obj.get("Date")
    if not date_str:
        return jsonify({"error": "Missing Date in uploaded report"}), 400

    try:
        d = _parse_report_date(date_str)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    new_entries = _entries_from_uploaded_report(report_obj)

    path = _report_path(d)
    lock_path = path.with_suffix(path.suffix + ".lock")

    with _file_lock(lock_path):
        existing = _load_gz_json(path) if path.exists() else {}
        merged = _merge_entries(existing, d, new_entries)
        _atomic_save_gz_json(path, merged)

    return jsonify({
        "status": "ok",
        "date": d.isoformat(),
        "entries_added": len(new_entries),
        "total_entries": len(merged["Entries"]),
        "file": str(path),
    })


@api_bp.get("/raports/day")
def reports_get_day_json():
    """
    Pobiera raport jako JSON (serwer rozpakowuje json.gz).
    /raports/day?date=YYYY-MM-DD
    """
    date_str = request.args.get("date", "")
    if not date_str:
        return jsonify({"error": "Missing query param: date=YYYY-MM-DD"}), 400

    try:
        d = _parse_report_date(date_str)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    path = _report_path(d)
    if not path.exists():
        return jsonify({"error": "Report not found"}), 404

    # Read-only (bez locka ok). Jeśli chcesz 100% spójności przy wysokiej konkurencji,
    # możesz też tu użyć _file_lock(lock_path).
    report = _load_gz_json(path)
    report = _ensure_report_shape(d, report)

    return jsonify(report)


@api_bp.get("/raports/download")
def reports_download_gz():
    """
    Pobiera surowy plik json.gz
    /raports/download?date=YYYY-MM-DD
    """
    date_str = request.args.get("date", "")
    if not date_str:
        return jsonify({"error": "Missing query param: date=YYYY-MM-DD"}), 400

    try:
        d = _parse_report_date(date_str)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    path = _report_path(d)
    if not path.exists():
        return jsonify({"error": "Report not found"}), 404

    return send_file(
        path,
        mimetype="application/gzip",
        as_attachment=True,
        download_name=path.name,
    )


@api_bp.get("/raports/list")
def reports_list():
    """
    Lista raportów.
    Opcjonalne filtry:
      /raports/list?year=2026&month=01
    """
    year = request.args.get("year")
    month = request.args.get("month")

    base = RAPORTS_DIR
    if year:
        base = base / str(year).zfill(4)
    if month:
        base = base / str(month).zfill(2)

    if not base.exists():
        return jsonify({"Items": []})

    items = []
    for p in sorted(base.rglob("*.json.gz")):
        # nazwa pliku: YYYY-MM-DD.json.gz -> stem daje "YYYY-MM-DD.json"
        # więc usuwamy końcówkę ".json"
        date_part = p.name.replace(".json.gz", "")
        items.append({
            "Date": date_part,
            "Path": str(p),
            "SizeBytes": p.stat().st_size,
        })

    return jsonify({"Items": items})


@api_bp.get("/raports/exists")
def reports_exists():
    """
    Szybki check czy raport istnieje.
    /raports/exists?date=YYYY-MM-DD
    """
    date_str = request.args.get("date", "")
    if not date_str:
        return jsonify({"error": "Missing query param: date=YYYY-MM-DD"}), 400

    try:
        d = _parse_report_date(date_str)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    path = _report_path(d)
    return jsonify({"Date": d.isoformat(), "Exists": path.exists()})
