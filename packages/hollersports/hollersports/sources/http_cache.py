"""Simple file-backed HTTP GET cache with TTL (advisory fetch polish)."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


def _cache_path(cache_dir: Path, url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
    return cache_dir / f"{digest}.json"


def cached_get_json(
    url: str,
    *,
    cache_dir: str | Path = "data/http_cache",
    ttl_seconds: float = 300.0,
    timeout_s: float = 20.0,
    headers: dict[str, str] | None = None,
) -> Any:
    """GET JSON with disk cache. Returns parsed JSON. Raises on hard failures after cache miss."""
    root = Path(cache_dir)
    root.mkdir(parents=True, exist_ok=True)
    path = _cache_path(root, url)
    now = time.time()
    if path.is_file():
        try:
            blob = json.loads(path.read_text(encoding="utf-8"))
            if now - float(blob.get("fetched_at", 0)) <= float(ttl_seconds):
                return blob.get("body")
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass

    req = Request(url, headers=headers or {"User-Agent": "HollerSports-advisory/0.3"})
    with urlopen(req, timeout=timeout_s) as resp:  # noqa: S310 — caller supplies fixed HTTPS URLs
        raw = resp.read().decode("utf-8")
    body = json.loads(raw)
    path.write_text(
        json.dumps({"fetched_at": now, "url": url, "body": body}, sort_keys=True),
        encoding="utf-8",
    )
    return body
