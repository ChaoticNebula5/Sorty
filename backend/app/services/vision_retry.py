"""Bounded provider retries. Never expose API response bodies or credentials."""
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import logging
import random
import time
from typing import Callable, TypeVar

import httpx

logger = logging.getLogger(__name__)
T = TypeVar("T")


class VisionRetryExhausted(RuntimeError):
    pass


class VisionQuotaExhausted(VisionRetryExhausted):
    pass


def error_code(error: Exception) -> int | None:
    value = getattr(error, "code", None)
    if value is None:
        value = getattr(getattr(error, "response", None), "status_code", None)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def error_details(error: Exception) -> list[dict]:
    payload = getattr(error, "details", None) or getattr(error, "response_json", None)
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    body = payload.get("error", payload)
    details = body.get("details", []) if isinstance(body, dict) else []
    return details if isinstance(details, list) else []


def daily_quota_exhausted(error: Exception) -> bool:
    if error_code(error) != 429:
        return False
    # Inspect quota IDs/metrics, rather than interpreting every 429 as daily quota.
    for detail in error_details(error):
        if not isinstance(detail, dict):
            continue
        for violation in detail.get("violations", []) or []:
            if not isinstance(violation, dict):
                continue
            identifier = str(violation.get("quotaId", "")) + str(violation.get("quotaMetric", ""))
            normalized = identifier.lower().replace("_", "")
            if "perday" in normalized or "daily" in normalized or str(violation.get("quotaValue", "")) == "0":
                return True
    return False


def retry_after(error: Exception) -> float:
    delays = [0.0]
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", {})
    header = headers.get("Retry-After") if headers else None
    if header:
        try:
            delays.append(float(header))
        except (TypeError, ValueError):
            try:
                delays.append((parsedate_to_datetime(header) - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                pass
    for detail in error_details(error):
        if isinstance(detail, dict) and str(detail.get("@type", "")).endswith("RetryInfo"):
            try:
                delays.append(float(str(detail["retryDelay"]).removesuffix("s")))
            except (KeyError, ValueError, TypeError):
                pass
    return max(delays)


def call_with_backoff(
    operation: Callable[[], T], *, max_attempts: int,
    base_delay: float, max_delay: float, wait_budget: float,
) -> T:
    waited = 0.0
    for attempt in range(max_attempts):
        try:
            return operation()
        except Exception as error:
            if daily_quota_exhausted(error):
                raise VisionQuotaExhausted("Gemini daily or unavailable quota exhausted. Retry after quota resets or configuration changes.") from error
            code = error_code(error)
            transient = code in {408, 429, 500, 502, 503, 504} or isinstance(error, httpx.TransportError)
            if not transient:
                raise
            delay = max(retry_after(error), random.uniform(0, min(max_delay, base_delay * 2**attempt)))
            if attempt + 1 == max_attempts or waited + delay > wait_budget:
                raise VisionRetryExhausted("Gemini temporary errors exceeded the retry budget. Retry failed images later.") from error
            logger.warning(
                "Temporary vision error (status=%s, type=%s); retry %s/%s in %.2fs",
                code, type(error).__name__, attempt + 2, max_attempts, delay,
            )
            time.sleep(delay)
            waited += delay
