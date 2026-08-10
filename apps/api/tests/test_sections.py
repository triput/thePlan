"""API tests for sections CRUD scoped by project."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient


def _uid() -> str:
    return uuid.uuid4().hex[:8]


def _create_project(client: TestClient) -> dict:
    response = client.post(
        "/api/v1/projects",
        json={"title": f"proj-{_uid()}", "color_hex": "#0A8558"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_sections_crud_scoped_by_project(client: TestClient) -> None:
    project_a = _create_project(client)
    project_b = _create_project(client)

    create = client.post(
        "/api/v1/sections",
        json={"project_id": project_a["id"], "title": f"Backlog {_uid()}", "sort_order": 1},
    )
    assert create.status_code == 201, create.text
    section = create.json()
    assert section["project_id"] == project_a["id"]

    listed_a = client.get("/api/v1/sections", params={"project_id": project_a["id"]})
    assert listed_a.status_code == 200
    ids_a = {item["id"] for item in listed_a.json()["items"]}
    assert section["id"] in ids_a

    listed_b = client.get("/api/v1/sections", params={"project_id": project_b["id"]})
    assert listed_b.status_code == 200
    ids_b = {item["id"] for item in listed_b.json()["items"]}
    assert section["id"] not in ids_b

    patched = client.patch(
        f"/api/v1/sections/{section['id']}",
        json={"title": f"Ready {_uid()}"},
    )
    assert patched.status_code == 200
    assert patched.json()["title"].startswith("Ready")

    got = client.get(f"/api/v1/sections/{section['id']}")
    assert got.status_code == 200
    assert got.json()["id"] == section["id"]

    deleted = client.delete(f"/api/v1/sections/{section['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/sections/{section['id']}").status_code == 404


def test_list_sections_unknown_project_404(client: TestClient) -> None:
    response = client.get(
        "/api/v1/sections",
        params={"project_id": str(uuid.uuid4())},
    )
    assert response.status_code == 404


def test_create_section_unknown_project_404(client: TestClient) -> None:
    response = client.post(
        "/api/v1/sections",
        json={"project_id": str(uuid.uuid4()), "title": "Orphan"},
    )
    assert response.status_code == 404
