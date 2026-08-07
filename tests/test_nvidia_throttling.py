"""Tests for NVIDIA NIM throttling behaviour.

Production hit "ResourceExhausted: Worker local total request limit reached
(17/16)" and plain 429s. With no retry those returned None, and every caller
silently fell back to rule-based output.
"""

import threading
from unittest.mock import patch

import pytest

import llm_summary


class _Resp:
    def __init__(self, status, body=None, headers=None, text=""):
        self.status_code = status
        self._body = body or {}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._body


def _ok(content="answer"):
    return _Resp(200, {"choices": [{"message": {"content": content}}]})


@pytest.fixture(autouse=True)
def _no_real_sleeping():
    with patch("llm_summary.time.sleep") as slept:
        yield slept


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    monkeypatch.setenv("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")


def test_a_throttled_call_is_retried_and_succeeds():
    responses = [_Resp(429, text="Too Many Requests"), _ok("recovered")]
    with patch("llm_summary.requests.post", side_effect=responses) as post:
        result = llm_summary.query_nvidia("hi")

    assert result == "recovered"
    assert post.call_count == 2


def test_the_concurrency_error_is_retried():
    """503 ResourceExhausted is the exact production failure."""
    body = "ResourceExhausted: Worker local total request limit reached (17/16)"
    with patch("llm_summary.requests.post",
               side_effect=[_Resp(503, text=body), _Resp(503, text=body), _ok()]) as post:
        assert llm_summary.query_nvidia("hi") == "answer"
    assert post.call_count == 3


def test_retry_after_is_honoured(_no_real_sleeping):
    with patch("llm_summary.requests.post",
               side_effect=[_Resp(429, headers={"Retry-After": "7"}), _ok()]):
        llm_summary.query_nvidia("hi")

    assert _no_real_sleeping.call_args[0][0] == 7


def test_a_dead_model_is_not_retried():
    """410 Gone is permanent; retrying wastes the quota that is left."""
    with patch("llm_summary.requests.post",
               side_effect=[_Resp(410, text="model reached end of life")]) as post:
        assert llm_summary.query_nvidia("hi") is None
    assert post.call_count == 1


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_client_errors_are_not_retried(status):
    with patch("llm_summary.requests.post", side_effect=[_Resp(status, text="nope")]) as post:
        assert llm_summary.query_nvidia("hi") is None
    assert post.call_count == 1


def test_retries_are_bounded():
    attempts = [_Resp(429, text="throttled")] * 20
    with patch("llm_summary.requests.post", side_effect=attempts) as post:
        assert llm_summary.query_nvidia("hi") is None

    assert post.call_count == llm_summary.NVIDIA_MAX_RETRIES + 1


def test_network_errors_are_retried():
    with patch("llm_summary.requests.post",
               side_effect=[ConnectionError("reset"), _ok("after reconnect")]) as post:
        assert llm_summary.query_nvidia("hi") == "after reconnect"
    assert post.call_count == 2


def test_the_request_timeout_allows_a_long_generation():
    """60s cut off a 70B model mid-pack and discarded the work."""
    captured = {}

    def capture(*args, **kwargs):
        captured.update(kwargs)
        return _ok()

    with patch("llm_summary.requests.post", side_effect=capture):
        llm_summary.query_nvidia("hi")

    assert captured["timeout"] >= 120, "a full creator pack does not finish in 60s"


def test_a_rate_limit_backs_off_further_than_a_transient_fault():
    """429 is a per-minute quota; ~12s against a 60s window burns the attempts."""
    rate_limited = max(llm_summary._retry_delay(3, status=429) for _ in range(20))
    transient = max(llm_summary._retry_delay(3, status=503) for _ in range(20))

    assert rate_limited > transient
    assert rate_limited >= 20, "must be on the scale of a per-minute window"


def test_backoff_grows_and_is_jittered():
    delays = {llm_summary._retry_delay(2) for _ in range(20)}
    assert len(delays) > 1, "identical delays make every worker retry in lockstep"
    assert max(delays) <= llm_summary.NVIDIA_BACKOFF_CAP
    assert min(llm_summary._retry_delay(0) for _ in range(20)) <= \
        max(llm_summary._retry_delay(3) for _ in range(20))


def test_concurrent_calls_are_capped():
    """More threads than slots must not produce more simultaneous requests."""
    peak = {"n": 0, "cur": 0}
    lock = threading.Lock()

    def slow_post(*args, **kwargs):
        with lock:
            peak["cur"] += 1
            peak["n"] = max(peak["n"], peak["cur"])
        # Event().wait is a real delay; time.sleep is patched out by the fixture.
        threading.Event().wait(0.02)
        with lock:
            peak["cur"] -= 1
        return _ok()

    with patch("llm_summary.requests.post", side_effect=slow_post):
        threads = [threading.Thread(target=llm_summary.query_nvidia, args=("hi",))
                   for _ in range(12)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    assert peak["n"] <= llm_summary.NVIDIA_MAX_CONCURRENCY, \
        f"{peak['n']} concurrent calls exceeded the cap"
