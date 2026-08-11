"""Small, dependency-free TTL cache for read-heavy API queries."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from functools import wraps
import os
from threading import RLock
from time import monotonic
from typing import Any, Callable


@dataclass
class _Entry:
    value: Any
    expires_at: float


class TTLCache:
    """Thread-safe bounded TTL cache that never exposes mutable cached values."""

    def __init__(self, max_size: int = 256):
        self.max_size = max_size
        self._entries: dict[tuple[Any, ...], _Entry] = {}
        self._lock = RLock()

    def get(self, key: tuple[Any, ...]) -> tuple[bool, Any]:
        now = monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return False, None
            if entry.expires_at <= now:
                self._entries.pop(key, None)
                return False, None
            return True, deepcopy(entry.value)

    def set(self, key: tuple[Any, ...], value: Any, ttl_seconds: float) -> None:
        with self._lock:
            if len(self._entries) >= self.max_size:
                oldest_key = min(
                    self._entries,
                    key=lambda item: self._entries[item].expires_at,
                )
                self._entries.pop(oldest_key, None)
            self._entries[key] = _Entry(
                value=deepcopy(value),
                expires_at=monotonic() + ttl_seconds,
            )

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


query_cache = TTLCache(max_size=int(os.getenv("COFC_QUERY_CACHE_MAX_SIZE", "256")))


def ttl_cached(ttl_seconds: float | None = None):
    """Cache a pure query function by positional and keyword arguments."""
    configured_ttl = float(os.getenv("COFC_QUERY_CACHE_TTL_SECONDS", "60"))
    ttl = configured_ttl if ttl_seconds is None else ttl_seconds

    def decorate(func: Callable):
        @wraps(func)
        def wrapped(*args, **kwargs):
            key = (func.__module__, func.__qualname__, args, tuple(sorted(kwargs.items())))
            found, value = query_cache.get(key)
            if found:
                return value
            value = func(*args, **kwargs)
            query_cache.set(key, value, ttl)
            return deepcopy(value)

        wrapped.cache_clear = query_cache.clear
        return wrapped

    return decorate
