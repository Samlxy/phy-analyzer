from __future__ import annotations

"""Tiny disk cache for API-Football GET responses.

Why: the free RapidAPI tier has a ~100 req/day quota, and a single day's
analyze pass makes 3N+ requests (fixtures list + per-team last-N + odds per fixture).
During backtests and reruns we want identical queries to be free.

Design:
- Keyed by SHA256(path + sorted query params).
- Files live under `var/cache/api_football/` as JSON blobs.
- TTL is per-path: fixtures lists and odds can change intraday, but historical
  `/fixtures?id=...` and `/fixtures/headtohead` for past matches are effectively
  immutable — configured below in `_TTLS`.
"""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any


_TTLS: dict[str, int] = {
    # seconds; override per path prefix. 0 == never expire.
    "/fixtures/headtohead": 0,
    "/odds": 60 * 30,       # 30 min
    "/fixtures": 60 * 10,   # 10 min for "today" lists; past days re-hit are rare
}

_DEFAULT_TTL = 60 * 30


def _ttl_for(path: str) -> int:
    for prefix, ttl in _TTLS.items():
        if path.startswith(prefix):
            return ttl
    return _DEFAULT_TTL


def _key(path: str, params: dict[str, Any]) -> str:
    canonical = path + "?" + "&".join(f"{k}={params[k]}" for k in sorted(params))
    return hashlib.sha256(canonical.encode()).hexdigest()


class DiskCache:
    def __init__(self, root: str | os.PathLike):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self.root / f"{key}.json"

    def get(self, path: str, params: dict[str, Any]) -> Any | None:
        p = self._path(_key(path, params))
        if not p.exists():
            return None
        try:
            blob = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError):
            return None
        ttl = _ttl_for(path)
        if ttl and (time.time() - blob.get("_t", 0)) > ttl:
            return None
        return blob.get("data")

    def set(self, path: str, params: dict[str, Any], data: Any) -> None:
        p = self._path(_key(path, params))
        p.write_text(json.dumps({"_t": time.time(), "data": data}))
