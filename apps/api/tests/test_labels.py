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


def test_list_labels_includes_task_count(client: TestClient) -> None:
    uid = _uid()
    label = client.post("/api/v1/labels", json={"name": f"counted-{uid}"}).json()
    client.post(
        "/api/v1/tasks",
        json={"title": f"task-a-{uid}", "label_ids": [label["id"]]},
    )
    client.post(
        "/api/v1/tasks",
        json={"title": f"task-b-{uid}", "label_ids": [label["id"]]},
    )

    response = client.get("/api/v1/labels")
    assert response.status_code == 200
    items = response.json()["items"]
    match = next(item for item in items if item["id"] == label["id"])
    assert match["task_count"] == 2


def test_batch_create_labels_success(client: TestClient) -> None:
    uid = _uid()
    response = client.post(
        "/api/v1/labels/batch",
        json={
            "labels": [
                {"name": f"Batch-A-{uid}", "color_hex": "#111111"},
                {"name": f"Batch-B-{uid}", "color_hex": "#222222"},
            ]
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["items"]) == 2
    assert body["skipped"] == []
    names = {item["name"] for item in body["items"]}
    assert names == {f"batch-a-{uid}", f"batch-b-{uid}"}


def test_batch_create_skips_duplicates(client: TestClient) -> None:
    uid = _uid()
    existing = client.post("/api/v1/labels", json={"name": f"existing-{uid}"}).json()

    response = client.post(
        "/api/v1/labels/batch",
        json={
            "labels": [
                {"name": f"existing-{uid}".upper()},
                {"name": f"new-{uid}"},
                {"name": f"new-{uid}".upper()},
            ]
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["name"] == f"new-{uid}"
    assert len(body["skipped"]) == 2
    skipped_by_name = {entry["name"]: entry["reason"] for entry in body["skipped"]}
    assert skipped_by_name[existing["name"]] == "LABEL_DUPLICATE"
    assert skipped_by_name[f"new-{uid}"] == "duplicate_in_request"


def test_batch_create_skips_empty_names(client: TestClient) -> None:
    uid = _uid()
    response = client.post(
        "/api/v1/labels/batch",
        json={
            "labels": [
                {"name": "   "},
                {"name": f"valid-{uid}"},
            ]
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["name"] == f"valid-{uid}"
    assert body["skipped"] == [{"name": "", "reason": "LABEL_NAME_EMPTY"}]
