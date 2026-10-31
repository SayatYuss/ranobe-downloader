"""HTTP retry helpers for transient API failures and rate limiting."""
from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import random
import time

import httpx


def retry_after_seconds(value: str | None, now: datetime | None = None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            now = now or datetime.now(timezone.utc)
            return max(0.0, (date - now).total_seconds())
        except (ValueError, TypeError, OverflowError):
            return None


def with_retries(operation, *, attempts: int = 5, sleep=time.sleep):
    """Retry 429, 500, 502, 503, and 504. Stop on other errors."""
    if attempts < 1:
        raise ValueError("attempts must be positive")
    for index in range(attempts):
        try:
            return operation()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status not in (429, 500, 502, 503, 504) or index == attempts - 1:
                raise
            retry_after = retry_after_seconds(exc.response.headers.get("Retry-After"))
            delay = retry_after if retry_after is not None else min(120.0, 2 ** (index + 1) + random.random())
            print(f"HTTP {status}: retry in {delay:.1f}s ({index + 1}/{attempts - 1})")
            sleep(delay)
        except (httpx.TimeoutException, httpx.NetworkError):
            if index == attempts - 1:
                raise
            sleep(min(120.0, 2 ** (index + 1) + random.random()))
