from __future__ import annotations

from typing import Any

from more.transaction import default_commit_veto


def callFUT(response: Any) -> bool:
    return default_commit_veto(None, response)


def test_it_true_500() -> None:
    response = DummyResponse("500 Server Error")
    assert callFUT(response)


def test_it_true_503() -> None:
    response = DummyResponse("503 Service Unavailable")
    assert callFUT(response)


def test_it_true_400() -> None:
    response = DummyResponse("400 Bad Request")
    assert callFUT(response)


def test_it_true_411() -> None:
    response = DummyResponse("411 Length Required")
    assert callFUT(response)


def test_it_false_200() -> None:
    response = DummyResponse("200 OK")
    assert not callFUT(response)


def test_it_false_201() -> None:
    response = DummyResponse("201 Created")
    assert not callFUT(response)


def test_it_false_301() -> None:
    response = DummyResponse("301 Moved Permanently")
    assert not callFUT(response)


def test_it_false_302() -> None:
    response = DummyResponse("302 Found")
    assert not callFUT(response)


def test_it_false_x_tm_commit() -> None:
    response = DummyResponse("200 OK", {"x-tm": "commit"})
    assert not callFUT(response)


def test_it_true_x_tm_abort() -> None:
    response = DummyResponse("200 OK", {"x-tm": "abort"})
    assert callFUT(response)


def test_it_true_x_tm_anythingelse() -> None:
    response = DummyResponse("200 OK", {"x-tm": ""})
    assert callFUT(response)


class DummyResponse:
    def __init__(
        self, status: str = "200 OK", headers: dict[str, str] | None = None
    ) -> None:
        self.status = status
        if headers is None:
            headers = {}
        self.headers = headers
