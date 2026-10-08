"""HTTP status → CLI exit mapping. No live API."""

from __future__ import annotations

import json

import httpx
import pytest

from theplan.api_client import api_error_from_response
from theplan.errors import exit_code_for_api_status


@pytest.mark.parametrize(
    ("status", "exit_code"),
    [
        (401, 2),
        (403, 2),
        (404, 3),
        (409, 5),
        (422, 1),
        (400, 4),
        (500, 4),
        (503, 4),
    ],
)
def test_exit_code_for_api_status(status: int, exit_code: int) -> None:
    assert exit_code_for_api_status(status) == exit_code


def test_api_error_from_json_body() -> None:
    response = httpx.Response(
        401,
        json={"detail": "Not authenticated", "code": "UNAUTHENTICATED"},
    )
    err = api_error_from_response(response)
    assert err.code == "UNAUTHENTICATED"
    assert err.message == "Not authenticated"
    assert err.exit_code == 2


def test_api_error_from_validation_list() -> None:
    detail = [{"loc": ["body", "password"], "msg": "field required"}]
    response = httpx.Response(422, json={"detail": detail})
    err = api_error_from_response(response)
    assert err.code == "VALIDATION_ERROR"
    assert err.exit_code == 1
    assert json.loads(err.message) == detail


def test_api_error_from_non_json_body() -> None:
    response = httpx.Response(502, content=b"bad gateway")
    err = api_error_from_response(response)
    assert err.code == "API_ERROR"
    assert err.exit_code == 4
    assert err.message == "bad gateway"
