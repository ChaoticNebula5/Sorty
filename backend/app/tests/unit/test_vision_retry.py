from types import SimpleNamespace

import httpx
import pytest
from google.genai.errors import APIError

from app.services import vision_retry as retry


def api_error(code, *, details=None, headers=None):
    return APIError(code, {"error": {"code": code, "message": "private provider message", "details": details or []}},
                    response=httpx.Response(code, headers=headers))


def run(operation, **overrides):
    return retry.call_with_backoff(operation, **{
        "max_attempts": 4, "base_delay": 2, "max_delay": 30, "wait_budget": 120, **overrides,
    })


@pytest.fixture
def waits(monkeypatch):
    values = []
    monkeypatch.setattr(retry.time, "sleep", values.append)
    monkeypatch.setattr(retry.random, "uniform", lambda lower, upper: upper)
    return values


@pytest.mark.parametrize("code", [408, 429, 500, 502, 503, 504])
def test_transient_failure_recovers_with_exponential_backoff(code, waits):
    calls = []
    def operation():
        calls.append(1)
        if len(calls) < 3:
            raise api_error(code)
        return "image analysis"
    assert run(operation) == "image analysis"
    assert len(calls) == 3
    assert waits == [2, 4]


@pytest.mark.parametrize("code", [400, 401, 402, 403, 404, 501])
def test_permanent_errors_are_not_retried(code, waits):
    error = api_error(code)
    with pytest.raises(APIError) as raised:
        run(lambda: (_ for _ in ()).throw(error))
    assert raised.value is error
    assert waits == []


def test_exhaustion_is_bounded_and_does_not_expose_provider_message(waits):
    calls = []
    def operation():
        calls.append(1)
        raise api_error(503)
    with pytest.raises(retry.VisionRetryExhausted, match="retry budget") as raised:
        run(operation)
    assert len(calls) == 4
    assert waits == [2, 4, 8]
    assert "private" not in str(raised.value)


@pytest.mark.parametrize("quota", [
    {"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"},
    {"quotaMetric": "generativelanguage.googleapis.com/generate_content_requests_per_day"},
    {"quotaId": "RequestsPerMinute", "quotaValue": "0"},
])
def test_daily_or_zero_quota_stops_without_retry(quota, waits):
    with pytest.raises(retry.VisionQuotaExhausted):
        run(lambda: (_ for _ in ()).throw(api_error(429, details=[{"violations": [quota]}])))
    assert waits == []


def test_google_retry_info_and_http_retry_after_are_both_respected(waits):
    calls = []
    def operation():
        calls.append(1)
        if len(calls) == 1:
            raise api_error(429, headers={"Retry-After": "5"}, details=[
                {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "7.5s"}
            ])
        return "ok"
    assert run(operation) == "ok"
    assert waits == [7.5]


def test_provider_delay_over_budget_pauses_instead_of_retrying_early(waits):
    with pytest.raises(retry.VisionRetryExhausted):
        run(lambda: (_ for _ in ()).throw(api_error(429, headers={"Retry-After": "3600"})))
    assert waits == []


def test_network_timeout_is_retried_and_delay_is_capped(waits):
    calls = []
    def operation():
        calls.append(1)
        if len(calls) < 4:
            raise httpx.ReadTimeout("timeout")
        return "ok"
    assert run(operation, max_delay=3) == "ok"
    assert waits == [2, 3, 3]


def test_invalid_model_output_is_not_retried(waits):
    with pytest.raises(ValueError, match="invalid JSON"):
        run(lambda: (_ for _ in ()).throw(ValueError("invalid JSON")))
    assert waits == []


def test_total_wait_budget_is_enforced_across_attempts(waits):
    with pytest.raises(retry.VisionRetryExhausted):
        run(lambda: (_ for _ in ()).throw(api_error(429)), wait_budget=10)
    assert waits == [2, 4]


def test_jitter_uses_a_bounded_random_delay(monkeypatch):
    waits = []
    monkeypatch.setattr(retry.time, "sleep", waits.append)
    bounds = []
    monkeypatch.setattr(retry.random, "uniform", lambda a, b: bounds.append((a, b)) or b / 2)
    with pytest.raises(retry.VisionRetryExhausted):
        run(lambda: (_ for _ in ()).throw(api_error(503)), max_attempts=3)
    assert waits == [1, 2]
    assert bounds[:2] == [(0, 2), (0, 4)]
