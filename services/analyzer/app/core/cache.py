from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from app.core.config import settings

DEFAULT_TTL_S = 7 * 24 * 3600


def _path_for(namespace: str, key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    directory = settings.cache_dir / namespace
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{digest}.json"


def cache_get(namespace: str, key: str, ttl_s: int = DEFAULT_TTL_S) -> Any | None:
    path = _path_for(namespace, key)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if time.time() - payload.get("stored_at", 0) > ttl_s:
        return None
    return payload.get("data")


def cache_put(namespace: str, key: str, data: Any) -> None:
    path = _path_for(namespace, key)
    payload = {"stored_at": time.time(), "data": data}
    try:
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
