import hmac
import os
import re
import secrets
import threading
import time
from hashlib import sha256
from typing import Dict, Optional, Tuple


DEFAULT_PUBLIC_STATS_ORIGINS = (
    "https://stem.zis3c.dev",
    "https://stemusas.com",
    "https://www.stemusas.com",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
)
_PAGES_PREVIEW_RE = re.compile(r"^https://[a-z0-9-]+\.stem-usas\.pages\.dev$")


def is_allowed_public_stats_origin(origin: Optional[str]) -> bool:
    if not origin:
        return False
    clean = origin.strip().rstrip("/")
    raw_env = os.getenv("PUBLIC_STATS_CORS_ORIGINS", "")
    allowed = (
        tuple(o.strip().rstrip("/") for o in raw_env.split(",") if o.strip())
        if raw_env.strip()
        else DEFAULT_PUBLIC_STATS_ORIGINS
    )
    if clean in allowed:
        return True
    return bool(_PAGES_PREVIEW_RE.match(clean))


def build_public_stats_headers(origin: Optional[str]) -> Dict[str, str]:
    headers = {
        "Cache-Control": "public, max-age=300",
        "X-Content-Type-Options": "nosniff",
        "Vary": "Origin",
    }
    if origin and is_allowed_public_stats_origin(origin):
        headers["Access-Control-Allow-Origin"] = origin.strip().rstrip("/")
        headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
        headers["Access-Control-Max-Age"] = "86400"
    return headers


_REPORTS: Dict[str, dict] = {}
_PROFILE_REPORTS: Dict[str, dict] = {}
_PROFILE_LATEST_BY_SUBJECT: Dict[str, str] = {}
_LOCK = threading.Lock()


def _secret_key() -> str:
    # Priority: dedicated secret -> webhook secret -> bot token.
    return (
        os.getenv("STATS_LINK_SECRET", "").strip()
        or os.getenv("TELEGRAM_WEBHOOK_SECRET", "").strip()
        or os.getenv("TELEGRAM_TOKEN", "").strip()
        or "fallback-insecure-dev-key"
    )


def _sign(message: str) -> str:
    return hmac.new(_secret_key().encode("utf-8"), message.encode("utf-8"), sha256).hexdigest()


def _cleanup_expired(now_ts: Optional[int] = None) -> None:
    now = int(now_ts or time.time())
    stale = [k for k, v in _REPORTS.items() if int(v.get("exp", 0)) < now]
    for key in stale:
        _REPORTS.pop(key, None)


def create_demographic_report(payload: dict, ttl_seconds: int = 900) -> str:
    now = int(time.time())
    exp = now + max(60, int(ttl_seconds))
    nonce = secrets.token_urlsafe(16)
    signed = f"{nonce}.{exp}"
    sig = _sign(signed)
    token = f"{signed}.{sig}"
    with _LOCK:
        _cleanup_expired(now)
        # Security/UX policy: only the latest generated report link remains valid.
        # This ensures older links expire immediately once a new report is generated.
        _REPORTS.clear()
        _REPORTS[nonce] = {
            "exp": exp,
            "payload": payload,
        }
    return token


def read_demographic_report(token: str) -> Tuple[Optional[dict], Optional[str]]:
    try:
        nonce, exp_raw, sig = token.split(".", 2)
        exp = int(exp_raw)
    except Exception:
        return None, "invalid_token"

    signed = f"{nonce}.{exp}"
    expected = _sign(signed)
    if not hmac.compare_digest(sig, expected):
        return None, "bad_signature"

    now = int(time.time())
    if exp < now:
        return None, "expired"

    with _LOCK:
        _cleanup_expired(now)
        entry = _REPORTS.get(nonce)
        if not entry:
            return None, "not_found"
        if int(entry.get("exp", 0)) != exp:
            return None, "mismatch"
        return entry.get("payload"), None


def _cleanup_expired_profiles(now_ts: Optional[int] = None) -> None:
    now = int(now_ts or time.time())
    stale = [k for k, v in _PROFILE_REPORTS.items() if int(v.get("exp", 0)) < now]
    for key in stale:
        subject = str(_PROFILE_REPORTS.get(key, {}).get("subject", ""))
        _PROFILE_REPORTS.pop(key, None)
        if subject and _PROFILE_LATEST_BY_SUBJECT.get(subject) == key:
            _PROFILE_LATEST_BY_SUBJECT.pop(subject, None)


def create_member_profile_report(
    payload: dict,
    subject: str,
    ttl_seconds: int = 1200,
) -> str:
    now = int(time.time())
    exp = now + max(60, int(ttl_seconds))
    nonce = secrets.token_urlsafe(16)
    signed = f"{nonce}.{exp}"
    sig = _sign(signed)
    token = f"{signed}.{sig}"
    subject_key = str(subject or "").strip().upper() or "__UNKNOWN__"

    with _LOCK:
        _cleanup_expired_profiles(now)
        prev_nonce = _PROFILE_LATEST_BY_SUBJECT.get(subject_key)
        if prev_nonce:
            _PROFILE_REPORTS.pop(prev_nonce, None)
        _PROFILE_REPORTS[nonce] = {
            "exp": exp,
            "payload": payload,
            "subject": subject_key,
        }
        _PROFILE_LATEST_BY_SUBJECT[subject_key] = nonce
    return token


def read_member_profile_report(token: str) -> Tuple[Optional[dict], Optional[str]]:
    try:
        nonce, exp_raw, sig = token.split(".", 2)
        exp = int(exp_raw)
    except Exception:
        return None, "invalid_token"

    signed = f"{nonce}.{exp}"
    expected = _sign(signed)
    if not hmac.compare_digest(sig, expected):
        return None, "bad_signature"

    now = int(time.time())
    if exp < now:
        return None, "expired"

    with _LOCK:
        _cleanup_expired_profiles(now)
        entry = _PROFILE_REPORTS.get(nonce)
        if not entry:
            return None, "not_found"
        if int(entry.get("exp", 0)) != exp:
            return None, "mismatch"
        return entry.get("payload"), None
