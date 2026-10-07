from __future__ import annotations

import threading
from typing import Callable

_MAX_ACTIVE_PER_IP = 1
_MAX_ACTIVE_TOTAL = 20
_lock = threading.Lock()


class RateLimitError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def check_can_start(
    client_ip: str,
    is_active_for_ip: Callable[[str], bool],
    active_total: int,
) -> None:
    with _lock:
        if active_total >= _MAX_ACTIVE_TOTAL:
            raise RateLimitError("Too many scans are in progress. Try again shortly.")
        if is_active_for_ip(client_ip):
            raise RateLimitError("You already have an active scan. Wait for it to finish.")
