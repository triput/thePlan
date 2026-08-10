# thePlan API

FastAPI + SQLAlchemy 2 + Alembic backend for the personal task app.

## Prerequisites

- Python 3.12+
- PostgreSQL 16 (local or via Docker Compose)

## Local development

```powershell
cd apps/api
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Copy env and point at your Postgres
copy .env.example .env

# Run migrations
alembic upgrade head

# Start API (bootstrap user + system views seeded on startup)
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

## Key endpoints

| Method | Path | Notes |
|--------|------|-------|
| GET | `/health` | `{ "status": "ok" }` |
| GET | `/api/v1/auth/me` | Bootstrap user `local@localhost` |
| GET/POST | `/api/v1/epics` | List/create epics |
| GET/POST | `/api/v1/projects` | List/create projects |
| GET/POST | `/api/v1/tasks` | List/create tasks |
| GET/POST | `/api/v1/labels` | Names lowercased on write |

## Docker

Built via `infra/compose/compose.yaml` — see root README.
