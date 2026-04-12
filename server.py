"""
Authentication Server — Improved
Enhancements:
  - Rate limiting per IP
  - Input sanitization & strict validation
  - Cryptographically secure token/key generation
  - Atomic file writes (no data corruption on crash)
  - Structured JSON logging
  - Blueprint-based routing
  - Consistent error responses
  - Expired license auto-cleanup
  - /health endpoint
"""

import os
import json
import string
import random
import secrets
import logging
import tempfile
import hashlib
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict
from time import time

import yaml
from flask import Flask, request, jsonify, Blueprint
from pytz import timezone as tz

# ─── Config ──────────────────────────────────────────────────────────────────

with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)

AUTH_TOKEN = config["authtoken"]
PORT = config.get("port", 5000)
DB = "Database/Apps"
BASE = "Auth"

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","msg":%(message)s}',
    handlers=[logging.StreamHandler(), logging.FileHandler("auth.log")]
)
logger = logging.getLogger("auth")

def log_event(category: str, event: str, detail: str = "", color: int = 0):
    logger.info(f'"{category} | {event} | {detail.replace(chr(10), " ")}"')

# ─── Rate Limiter ─────────────────────────────────────────────────────────────

_rate_store: dict = defaultdict(list)

def rate_limit(max_requests: int = 30, window: int = 60):
    """Decorator: max_requests per window seconds per IP."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            ip = request.remote_addr
            now = time()
            _rate_store[ip] = [t for t in _rate_store[ip] if now - t < window]
            if len(_rate_store[ip]) >= max_requests:
                return jsonify({"error": "Too many requests"}), 429
            _rate_store[ip].append(now)
            return fn(*args, **kwargs)
        return wrapper
    return decorator

# ─── Auth middleware ───────────────────────────────────────────────────────────

def require_auth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        if not header or header != f"Bearer {AUTH_TOKEN}":
            log_event("api", "Unauthorized", f"IP:{request.remote_addr}", 0xFF0000)
            return jsonify({"error": "Unauthorized"}), 401
        return fn(*args, **kwargs)
    return wrapper

# ─── Helpers ──────────────────────────────────────────────────────────────────

ALPHABET = string.ascii_letters + string.digits

def secure_token(length: int = 16) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))

def secure_digits(length: int = 8) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))

def atomic_write(path: str, data: dict):
    """Write JSON atomically to avoid partial writes on crash."""
    dir_ = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(dir=dir_)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=4)
        os.replace(tmp, path)
    except Exception:
        os.unlink(tmp)
        raise

def load_json(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)

def expiry_from_duration(duration: str):
    now = datetime.utcnow()
    map_ = {"Month": timedelta(days=30), "Week": timedelta(days=7), "Day": timedelta(hours=24)}
    if duration == "Lifetime":
        return "Lifetime"
    return (now + map_[duration]).strftime("%Y-%m-%d %H:%M:%S")

def is_expired(expiry: str) -> bool:
    if expiry == "Lifetime":
        return False
    exp = datetime.strptime(expiry, "%Y-%m-%d %H:%M:%S")
    return datetime.utcnow() > exp

def sanitize_name(name: str) -> str:
    """Allow only alphanumeric, dash, underscore."""
    return "".join(c for c in name if c.isalnum() or c in "-_")

def find_license(license_key: str):
    """Return (app_name, active_licenses_dict, active_license_file_path) or (None,None,None)."""
    for app_folder in os.listdir(DB):
        app_dir = os.path.join(DB, app_folder)
        alp = os.path.join(app_dir, "active_license.json")
        if not os.path.exists(alp):
            continue
        try:
            data = load_json(alp)
            if isinstance(data, dict) and license_key in data:
                return app_folder, data, alp
        except (json.JSONDecodeError, OSError):
            continue
    return None, None, None

# ─── Blueprint ────────────────────────────────────────────────────────────────

auth = Blueprint("auth", __name__, url_prefix=f"/{BASE}")

# ── Health ────────────────────────────────────────────────────────────────────

@auth.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "ts": datetime.utcnow().isoformat()}), 200

@auth.route("/", methods=["GET"])
def index():
    return jsonify({"message": "Auth Server Running"}), 200

# ── Create App ────────────────────────────────────────────────────────────────

@auth.route("/create-app", methods=["POST"])
@require_auth
@rate_limit(20, 60)
def create_app():
    data = request.get_json(silent=True) or {}
    raw_name = data.get("app_name", "")
    app_name = sanitize_name(str(raw_name))
    version = str(data.get("version", "1.0"))
    link = data.get("link", "")

    if not app_name:
        return jsonify({"error": "Missing or invalid app_name"}), 400

    app_dir = os.path.join(DB, app_name)
    if os.path.exists(app_dir):
        return jsonify({"error": "App already exists"}), 409

    os.makedirs(app_dir, exist_ok=True)

    app_data = {
        "app_name": app_name,
        "app_secret": secure_token(16),
        "app_id": secure_digits(8),
        "version": version,
        "link": link,
        "created_at": datetime.utcnow().isoformat(),
    }
    atomic_write(os.path.join(app_dir, "app_info.json"), app_data)
    log_event("api", "App Created", f"App:{app_name} IP:{request.remote_addr}", 0x32CD32)
    return jsonify(app_data), 201

# ── Update Version ────────────────────────────────────────────────────────────

@auth.route("/update-version", methods=["POST"])
@require_auth
@rate_limit(30, 60)
def update_version():
    data = request.get_json(silent=True) or {}
    app_name = sanitize_name(str(data.get("app_name", "")))
    version = str(data.get("version", ""))
    link = data.get("link", "")

    if not app_name or not version:
        return jsonify({"error": "Missing app_name or version"}), 400

    path = os.path.join(DB, app_name, "app_info.json")
    if not os.path.exists(path):
        return jsonify({"error": "App not found"}), 404

    try:
        app_data = load_json(path)
        app_data["version"] = version
        app_data["link"] = link
        app_data["updated_at"] = datetime.utcnow().isoformat()
        atomic_write(path, app_data)
    except (json.JSONDecodeError, OSError):
        return jsonify({"error": "Failed to update app"}), 500

    log_event("api", "Version Updated", f"App:{app_name} v:{version}", 0x32CD32)
    return jsonify({"message": "Version and link updated"}), 200

# ── Generate License ──────────────────────────────────────────────────────────

VALID_DURATIONS = {"Month", "Week", "Lifetime", "Day"}

@auth.route("/gen-license", methods=["POST"])
@require_auth
@rate_limit(10, 60)
def gen_license():
    data = request.get_json(silent=True) or {}
    app_name = sanitize_name(str(data.get("app_name", "")))
    duration = data.get("duration", "")
    try:
        quantity = int(data.get("quantity", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Quantity must be an integer"}), 400

    if not app_name:
        return jsonify({"error": "Missing app_name"}), 400
    if duration not in VALID_DURATIONS:
        return jsonify({"error": f"Invalid duration. Choose from {VALID_DURATIONS}"}), 400
    if not 1 <= quantity <= 500:
        return jsonify({"error": "Quantity must be between 1 and 500"}), 400

    app_dir = os.path.join(DB, app_name)
    if not os.path.exists(app_dir):
        return jsonify({"error": "App not found"}), 404

    keys = [f"{app_name}-{duration[0]}-{secure_token(8)}" for _ in range(quantity)]
    unused_path = os.path.join(app_dir, "unused_license.txt")
    with open(unused_path, "a") as f:
        f.write("\n".join(keys) + "\n")

    log_event("api", "Licenses Generated", f"App:{app_name} qty:{quantity}", 0x32CD32)
    return jsonify({"message": f"{quantity} licenses generated", "keys": keys}), 201

# ── Assign License ────────────────────────────────────────────────────────────

@auth.route("/assign-license", methods=["POST"])
@require_auth
@rate_limit(20, 60)
def assign_license():
    data = request.get_json(silent=True) or {}
    app_name = sanitize_name(str(data.get("app_name", "")))
    duration = data.get("duration", "")

    if not app_name:
        return jsonify({"error": "Missing app_name"}), 400
    if duration not in VALID_DURATIONS:
        return jsonify({"error": "Invalid duration"}), 400

    app_dir = os.path.join(DB, app_name)
    unused_path = os.path.join(app_dir, "unused_license.txt")
    active_path = os.path.join(app_dir, "active_license.json")

    if not os.path.exists(app_dir):
        return jsonify({"error": "App not found"}), 404
    if not os.path.exists(unused_path):
        return jsonify({"error": "No unused licenses available"}), 404

    with open(unused_path, "r") as f:
        licenses = [l.strip() for l in f if l.strip()]

    key = next((k for k in licenses if f"-{duration[0]}-" in k), None)
    if not key:
        return jsonify({"error": f"No licenses available for {duration}"}), 404

    licenses.remove(key)
    with open(unused_path, "w") as f:
        f.write("\n".join(licenses) + ("\n" if licenses else ""))

    try:
        active = load_json(active_path) if os.path.exists(active_path) else {}
        if not isinstance(active, dict):
            active = {}
    except json.JSONDecodeError:
        active = {}

    expiry = expiry_from_duration(duration)
    active[key] = {"expiry": expiry, "user": None, "hwid": None, "assigned_at": datetime.utcnow().isoformat()}
    atomic_write(active_path, active)

    log_event("api", "License Assigned", f"Key:{key} App:{app_name}", 0x32CD32)
    return jsonify({"license": key, "expiry": expiry}), 200

# ── Verify License ────────────────────────────────────────────────────────────

@auth.route("/verify-license", methods=["GET"])
@require_auth
@rate_limit(60, 60)
def verify_license():
    license_key = request.args.get("license_key", "")
    app_name = sanitize_name(request.args.get("app_name", ""))
    app_secret = request.args.get("app_secret", "")
    hwid = request.args.get("hwid", "")
    version = request.args.get("version", "")

    if not all([license_key, app_name, app_secret, version]):
        return jsonify({"error": "Missing required parameters"}), 400

    app_dir = os.path.join(DB, app_name)
    info_path = os.path.join(app_dir, "app_info.json")
    active_path = os.path.join(app_dir, "active_license.json")

    if not os.path.exists(info_path):
        return jsonify({"error": "App not found"}), 404

    try:
        info = load_json(info_path)
    except json.JSONDecodeError:
        return jsonify({"error": "Corrupted app data"}), 500

    # Constant-time secret comparison
    if not secrets.compare_digest(info.get("app_secret", ""), app_secret):
        return jsonify({"error": "Invalid app secret"}), 401

    if not os.path.exists(active_path):
        return jsonify({"error": "No active licenses"}), 404

    try:
        active = load_json(active_path)
    except json.JSONDecodeError:
        return jsonify({"error": "Corrupted license data"}), 500

    ld = active.get(license_key)
    if not ld:
        return jsonify({"error": "License not found"}), 404

    if is_expired(ld["expiry"]):
        return jsonify({"error": "License expired"}), 403

    # HWID binding
    if not ld.get("hwid"):
        ld["hwid"] = hwid
        atomic_write(active_path, active)
    elif not secrets.compare_digest(ld["hwid"], hwid):
        return jsonify({"error": "HWID mismatch — different device"}), 403

    # Version check
    if version != info.get("version"):
        return jsonify({"error": "Outdated version", "link": info.get("link")}), 426

    log_event("api", "License Verified", f"Key:{license_key} App:{app_name}", 0x32CD32)
    return jsonify({"message": "License valid", "expiry": ld["expiry"], "hwid": ld["hwid"]}), 200

# ── Ban License ───────────────────────────────────────────────────────────────

@auth.route("/ban-license", methods=["POST"])
@require_auth
@rate_limit(20, 60)
def ban_license():
    data = request.get_json(silent=True) or {}
    key = data.get("license_key", "")
    if not key:
        return jsonify({"error": "Missing license_key"}), 400

    app_name, active, alp = find_license(key)
    if not app_name:
        return jsonify({"error": "License not found"}), 404

    del active[key]
    atomic_write(alp, active)
    log_event("api", "License Banned", f"Key:{key} App:{app_name}", 0xFF0000)
    return jsonify({"message": "License banned"}), 200

# ── Reset HWID ────────────────────────────────────────────────────────────────

@auth.route("/reset-hwid", methods=["POST"])
@require_auth
@rate_limit(10, 60)
def reset_hwid():
    data = request.get_json(silent=True) or {}
    key = data.get("license_key", "")
    user = str(data.get("user", ""))

    if not key or not user:
        return jsonify({"error": "Missing license_key or user"}), 400

    app_name, active, alp = find_license(key)
    if not app_name:
        return jsonify({"error": "License not found"}), 404

    ld = active[key]
    if not ld.get("user"):
        ld["user"] = user
    elif ld["user"] != user:
        # License sharing detected — ban it
        del active[key]
        atomic_write(alp, active)
        log_event("api", "License Sharing Detected — Banned", f"Key:{key}", 0xFF0000)
        return jsonify({"error": "License sharing detected, license banned"}), 403

    ld["hwid"] = None
    atomic_write(alp, active)
    log_event("api", "HWID Reset", f"Key:{key} User:{user}", 0x32CD32)
    return jsonify({"message": "HWID reset successfully"}), 200

# ── Update User ───────────────────────────────────────────────────────────────

@auth.route("/update-user", methods=["PATCH"])
@require_auth
@rate_limit(20, 60)
def update_user():
    data = request.get_json(silent=True) or {}
    key = data.get("license_key", "")
    user = str(data.get("user", ""))

    if not key or not user:
        return jsonify({"error": "Missing license_key or user"}), 400

    app_name, active, alp = find_license(key)
    if not app_name:
        return jsonify({"error": "License not found"}), 404

    active[key]["user"] = user
    atomic_write(alp, active)
    return jsonify({"message": "User updated"}), 200

# ── Get License ───────────────────────────────────────────────────────────────

@auth.route("/get-license", methods=["POST"])
@require_auth
@rate_limit(30, 60)
def get_license():
    data = request.get_json(silent=True) or {}
    key = data.get("license_key", "")
    if not key:
        return jsonify({"error": "Missing license_key"}), 400

    app_name, active, _ = find_license(key)
    if not app_name:
        return jsonify({"error": "License not found"}), 404

    ld = active[key]
    expiry = ld.get("expiry", "")

    if is_expired(expiry):
        return jsonify({"error": "License expired"}), 403

    return jsonify({
        "license_key": key,
        "app_name": app_name,
        "user": ld.get("user") or "Unassigned",
        "expiry_date": expiry,
        "hwid": ld.get("hwid") or "Not bound",
        "valid": True,
    }), 200

# ── Check Stats ───────────────────────────────────────────────────────────────

@auth.route("/check", methods=["GET"])
@require_auth
def check():
    total_apps = total_licenses = 0
    try:
        for folder in os.listdir(DB):
            alp = os.path.join(DB, folder, "active_license.json")
            if os.path.isdir(os.path.join(DB, folder)) and os.path.exists(alp):
                total_apps += 1
                try:
                    data = load_json(alp)
                    if isinstance(data, dict):
                        total_licenses += len(data)
                except json.JSONDecodeError:
                    pass
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"total_apps": total_apps, "total_licenses": total_licenses}), 200

# ── Cleanup expired licenses ──────────────────────────────────────────────────

@auth.route("/cleanup", methods=["POST"])
@require_auth
def cleanup():
    """Remove all expired licenses across all apps."""
    removed = 0
    for folder in os.listdir(DB):
        alp = os.path.join(DB, folder, "active_license.json")
        if not os.path.exists(alp):
            continue
        try:
            data = load_json(alp)
            before = len(data)
            data = {k: v for k, v in data.items() if not is_expired(v.get("expiry", "Lifetime"))}
            removed += before - len(data)
            atomic_write(alp, data)
        except (json.JSONDecodeError, OSError):
            pass
    return jsonify({"message": f"Removed {removed} expired licenses"}), 200

# ─── App Factory ──────────────────────────────────────────────────────────────

app = Flask(__name__)
app.register_blueprint(auth)
os.makedirs(DB, exist_ok=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT, debug=False)
