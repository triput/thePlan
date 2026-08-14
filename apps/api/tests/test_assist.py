"""Assist propose/apply tests — mock OpenAI-compat HTTP; no live Ollama."""

from __future__ import annotations

import json
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Label, Project, Task, User
from app.services import assist_llm


def _current_user(client: TestClient, db_session: Session) -> User:
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200, me.text
    user = db_session.get(User, uuid.UUID(me.json()["id"]))
    assert user is not None
    return user


def _patch_assist_httpx(monkeypatch: pytest.MonkeyPatch, handler: object) -> None:
    transport = httpx.MockTransport(handler)
    real_client = httpx.Client

    def _factory(*args: object, **kwargs: object) -> httpx.Client:
        kwargs["transport"] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(assist_llm.httpx, "Client", _factory)


def test_propose_returns_actions(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "actions": [
                                    {
                                        "type": "create_task",
                                        "title": "Buy oat milk",
                                        "priority": "p3",
                                        "label_names": ["errands"],
                                    }
                                ]
                            }
                        )
                    }
                }
            ]
        }
        return httpx.Response(200, json=payload)

    _patch_assist_httpx(monkeypatch, handler)
    res = client.post("/api/v1/assist/propose", json={"text": "remind me to buy oat milk"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["model"]
    assert len(body["actions"]) == 1
    assert body["actions"][0]["title"] == "Buy oat milk"
    assert body["actions"][0]["priority"] == "p3"
    assert body["actions"][0]["label_names"] == ["errands"]


def test_propose_unavailable_when_ollama_down(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    _patch_assist_httpx(monkeypatch, handler)
    res = client.post("/api/v1/assist/propose", json={"text": "add a task"})
    assert res.status_code == 503
    assert res.json()["code"] == "ASSIST_UNAVAILABLE"


def test_apply_creates_task_and_label(client: TestClient, db_session: Session) -> None:
    res = client.post(
        "/api/v1/assist/apply",
        json={
            "actions": [
                {
                    "type": "create_task",
                    "title": "Walk the dogs",
                    "priority": "p2",
                    "label_names": ["home"],
                }
            ]
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["ok"] is True
    assert body["results"][0]["created_labels"] == ["home"]
    task_id = body["results"][0]["task_id"]
    task = db_session.get(Task, uuid.UUID(task_id))
    assert task is not None
    assert task.title == "Walk the dogs"
    label = db_session.query(Label).filter(Label.name == "home").one()
    assert label is not None


def test_apply_resolves_project(client: TestClient, db_session: Session) -> None:
    user = _current_user(client, db_session)
    project = Project(owner_id=user.id, title="House", color_hex="#111111")
    db_session.add(project)
    db_session.flush()

    res = client.post(
        "/api/v1/assist/apply",
        json={
            "actions": [
                {
                    "type": "create_task",
                    "title": "Fix sink",
                    "project_name": "House",
                }
            ]
        },
    )
    assert res.status_code == 200, res.text
    task_id = res.json()["results"][0]["task_id"]
    task = db_session.get(Task, uuid.UUID(task_id))
    assert task is not None
    assert task.project_id == project.id


def test_assist_status(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    get_settings.cache_clear()

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/models")
        return httpx.Response(200, json={"data": [{"id": "llama3.2"}]})

    _patch_assist_httpx(monkeypatch, handler)
    res = client.get("/api/v1/assist/status")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["reachable"] is True
    assert body["model"]
