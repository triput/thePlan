"""Label delete with optional reassign/migrate."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _create_label(client: TestClient, name: str, color: str = "#635F75") -> dict:
    response = client.post("/api/v1/labels", json={"name": name, "color_hex": color})
    assert response.status_code == 201, response.text
    return response.json()


def _create_task_with_labels(client: TestClient, title: str, label_ids: list[str]) -> dict:
    response = client.post("/api/v1/tasks", json={"title": title, "label_ids": label_ids})
    assert response.status_code == 201, response.text
    return response.json()


def test_delete_label_without_body(client: TestClient) -> None:
    label = _create_label(client, "stale")
    task = _create_task_with_labels(client, "Tagged", [label["id"]])
    assert label["id"] in task["label_ids"]

    deleted = client.request("DELETE", f"/api/v1/labels/{label['id']}")
    assert deleted.status_code == 204, deleted.text

    listed = client.get("/api/v1/labels")
    assert all(item["id"] != label["id"] for item in listed.json()["items"])

    refreshed = client.get(f"/api/v1/tasks/{task['id']}")
    assert refreshed.status_code == 200
    assert label["id"] not in refreshed.json()["label_ids"]


def test_delete_reassign_one_and_many(client: TestClient) -> None:
    doomed = _create_label(client, "doomed")
    keep_a = _create_label(client, "keep-a", "#112233")
    keep_b = _create_label(client, "keep-b", "#445566")
    task = _create_task_with_labels(client, "Migrate me", [doomed["id"]])

    deleted = client.request(
        "DELETE",
        f"/api/v1/labels/{doomed['id']}",
        json={"reassign_to": [keep_a["id"], keep_b["id"]]},
    )
    assert deleted.status_code == 204, deleted.text

    refreshed = client.get(f"/api/v1/tasks/{task['id']}")
    ids = set(refreshed.json()["label_ids"])
    assert doomed["id"] not in ids
    assert keep_a["id"] in ids
    assert keep_b["id"] in ids


def test_delete_reassign_skips_already_tagged(client: TestClient) -> None:
    doomed = _create_label(client, "old-tag")
    keep = _create_label(client, "already")
    task = _create_task_with_labels(client, "Both", [doomed["id"], keep["id"]])

    deleted = client.request(
        "DELETE",
        f"/api/v1/labels/{doomed['id']}",
        json={"reassign_to": [keep["id"]]},
    )
    assert deleted.status_code == 204, deleted.text

    refreshed = client.get(f"/api/v1/tasks/{task['id']}")
    ids = refreshed.json()["label_ids"]
    assert ids.count(keep["id"]) == 1
    assert doomed["id"] not in ids


def test_delete_reassign_rejects_self(client: TestClient) -> None:
    label = _create_label(client, "selfish")
    response = client.request(
        "DELETE",
        f"/api/v1/labels/{label['id']}",
        json={"reassign_to": [label["id"]]},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "LABEL_REASSIGN_SELF"


def test_delete_reassign_rejects_missing(client: TestClient) -> None:
    label = _create_label(client, "lonely")
    missing = "00000000-0000-4000-8000-000000000099"
    response = client.request(
        "DELETE",
        f"/api/v1/labels/{label['id']}",
        json={"reassign_to": [missing]},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "LABEL_REASSIGN_NOT_FOUND"


def test_delete_label_404(client: TestClient) -> None:
    missing = "00000000-0000-4000-8000-000000000099"
    response = client.request("DELETE", f"/api/v1/labels/{missing}")
    assert response.status_code == 404
