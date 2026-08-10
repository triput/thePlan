"""API tests for label lowercase normalization and duplicate 409."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def test_create_label_lowercases_name(client: TestClient) -> None:
    name = f"Waiting-{_uid()}"
    response = client.post("/api/v1/labels", json={"name": name, "color_hex": "#635F75"})
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == name.lower()


def test_create_label_duplicate_case_insensitive_409(client: TestClient) -> None:
    base = f"focus-{_uid()}"
    first = client.post("/api/v1/labels", json={"name": base})
    assert first.status_code == 201

    second = client.post("/api/v1/labels", json={"name": base.upper()})
    assert second.status_code == 409
    body = second.json()
    assert body["code"] == "LABEL_DUPLICATE"
    assert "detail" in body


def test_update_label_duplicate_409(client: TestClient) -> None:
    a = client.post("/api/v1/labels", json={"name": f"alpha-{_uid()}"}).json()
    b = client.post("/api/v1/labels", json={"name": f"beta-{_uid()}"}).json()

    response = client.patch(f"/api/v1/labels/{b['id']}", json={"name": a["name"].upper()})
    assert response.status_code == 409
    assert response.json()["code"] == "LABEL_DUPLICATE"


def test_create_label_whitespace_only_rejected(client: TestClient) -> None:
    response = client.post("/api/v1/labels", json={"name": "   "})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "LABEL_NAME_EMPTY"
