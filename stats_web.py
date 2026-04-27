import hmac
import os
import secrets
import threading
import time
from hashlib import sha256
from typing import Dict, Optional, Tuple


_REPORTS: Dict[str, dict] = {}
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
