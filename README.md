# thePlan

Working docs and planning for a personal web-first task + scheduling app (**Phronesis Light** — conversational working name only).

Start here: [docs/README.md](docs/README.md)

## Quick start (Docker Compose)

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or any OCI-compatible runtime).

```powershell
docker compose -f infra/compose/compose.yaml up --build
```

| Service | URL |
|---------|-----|
| Web | http://localhost:8080 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Postgres | `localhost:5432` (user/db/password: `theplan`) |

Stop: `docker compose -f infra/compose/compose.yaml down`

## Local development (without Docker)

### 1. PostgreSQL

Run Postgres 16 locally or start only the database container:

```powershell
docker compose -f infra/compose/compose.yaml up postgres -d
```

### 2. API

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

### 3. Web

```powershell
cd apps/web
npm install
copy .env.example .env
npm run dev
```

Open http://localhost:5173

## Repository layout

```
apps/api/          FastAPI + SQLAlchemy 2 + Alembic
apps/web/          Vite + React + TypeScript
infra/compose/     Docker Compose stack
docs/              Product docs, ADRs, baseline SQL
```

## Wave 0 scope

Runnable hello-stack with CRUD stubs for epics, projects, tasks, and labels. Bootstrap user `local@localhost` with system smart views (Inbox, Today, Upcoming) seeded on API startup.
