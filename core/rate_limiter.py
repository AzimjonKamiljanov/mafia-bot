"""Lightweight in-memory token bucket rate limiter for anti-flood protection."""
import time
from typing import Dict, Tuple

_rate_limit_records: Dict[Tuple[int, str], list] = {}

def is_rate_limited(user_id: int, action: str = "cmd", max_rate: int = 5, window_seconds: float = 3.0) -> bool:
    """Check if user has exceeded max_rate actions within window_seconds.
    Returns True if rate limited (should be throttled), False otherwise.
    """
    now = time.time()
    key = (user_id, action)
    timestamps = _rate_limit_records.setdefault(key, [])

    # Filter out timestamps outside the sliding window
    cutoff = now - window_seconds
    timestamps = [t for t in timestamps if t > cutoff]

    if len(timestamps) >= max_rate:
        _rate_limit_records[key] = timestamps
        return True

    timestamps.append(now)
    _rate_limit_records[key] = timestamps
    return False

def reset_rate_limits():
    """Clear all rate limit records (useful for test isolation)."""
    _rate_limit_records.clear()
