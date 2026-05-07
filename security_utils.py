import ipaddress
import logging
import os
import re
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def env_bool(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, str(default))).strip().lower()
    return raw in ("1", "true", "yes", "on")


DEFAULT_TELEGRAM_IP_RANGES = (
    "149.154.160.0/20,91.108.4.0/22",
)


def parse_networks(raw: str) -> Tuple[ipaddress._BaseNetwork, ...]:
    items = []
    for token in (raw or "").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            items.append(ipaddress.ip_network(token, strict=False))
        except ValueError:
            logger.warning("SECURITY_EVENT INPUT_REJECT invalid CIDR '%s'", token)
    return tuple(items)


def extract_client_ip(
    remote_ip: str,
    x_forwarded_for: str,
    trust_proxy_hops: int,
) -> Optional[str]:
    remote_ip = (remote_ip or "").strip()
    if trust_proxy_hops <= 0 or not x_forwarded_for:
        return remote_ip or None

    chain = [part.strip() for part in x_forwarded_for.split(",") if part.strip()]
    if not chain:
        return remote_ip or None

    # Client IP sits before trusted proxy hops.
    idx = len(chain) - trust_proxy_hops - 1
    if idx < 0:
        return None
    return chain[idx]


def ip_allowed(ip_value: str, allowed_networks: Tuple[ipaddress._BaseNetwork, ...]) -> bool:
    if not ip_value:
        return False
    try:
        addr = ipaddress.ip_address(ip_value)
    except ValueError:
        return False
    return any(addr in net for net in allowed_networks)


class SlidingWindowLimiter:
    def __init__(self):
        self._lock = threading.Lock()
        self._bucket: Dict[str, Deque[float]] = defaultdict(deque)

    def check(self, key: str, window_sec: int, max_req: int) -> Tuple[bool, int]:
        now = time.time()
        w = max(1, int(window_sec))
        m = max(1, int(max_req))
        with self._lock:
            q = self._bucket[key]
            cutoff = now - w
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= m:
                retry = int(max(1, q[0] + w - now))
                return False, retry
            q.append(now)
        return True, 0


class SecurityMetrics:
    def __init__(self):
        self._lock = threading.Lock()
        self._counters = defaultdict(int)

    def inc(self, key: str) -> None:
        with self._lock:
            self._counters[key] += 1

    def snapshot(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._counters)


SECURITY_METRICS = SecurityMetrics()
RATE_LIMITER = SlidingWindowLimiter()


def log_security_event(tag: str, details: str = "") -> None:
    SECURITY_METRICS.inc(tag)
    clean = sanitize_sensitive_text(details)[:240]
    logger.warning("SECURITY_EVENT %s %s", tag, clean)


def sanitize_sensitive_text(value) -> str:
    text = str(value or "")
    text = re.sub(r"(?i)(token|secret|password|key)=([^\s&]+)", r"\1=***", text)
    text = re.sub(
        r'([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})',
        r"\1***@\2",
        text,
    )
    text = re.sub(r"\b\d{6,}\b", "***REDACTED***", text)
    text = re.sub(r"https?://\S+", "<url>", text)
    return text
