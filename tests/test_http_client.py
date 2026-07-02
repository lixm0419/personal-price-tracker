import logging

import pytest

from price_tracker.utils.http_client import HttpClient, HttpClientError


def test_http_client_passes_timeout_and_headers_to_transport():
    received = {}

    def transport(url, timeout, headers):
        received.update(url=url, timeout=timeout, headers=headers)
        return "<html>fixture</html>"

    client = HttpClient(
        timeout=3.5,
        user_agent="TestAgent/1.0",
        headers={"Accept-Language": "en"},
        transports={"fixture": transport},
    )
    assert client.fetch("fixture://product") == "<html>fixture</html>"
    assert received["timeout"] == 3.5
    assert received["headers"]["User-Agent"] == "TestAgent/1.0"
    assert received["headers"]["Accept-Language"] == "en"


def test_http_client_retries_then_succeeds(caplog):
    attempts = 0

    def transport(url, timeout, headers):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("slow response")
        return "ok"

    caplog.set_level(logging.WARNING)
    client = HttpClient(retries=1, transports={"fixture": transport})
    assert client.fetch("fixture://product") == "ok"
    assert attempts == 2
    assert "attempt 1/2" in caplog.text


def test_http_client_raises_clear_error_after_retries():
    def transport(url, timeout, headers):
        raise OSError("network unavailable")

    client = HttpClient(retries=1, transports={"fixture": transport})
    with pytest.raises(HttpClientError, match="after 2 attempt"):
        client.fetch("fixture://product")
