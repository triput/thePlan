# thePlan

Personal web-first task + scheduling app alongside the Synesis/Phronesis suite.

**Wave 1 (MVP) exited 2026-08-10.** Next: [Wave 1.5](docs/07-wave-roadmap.md). Exit record: [docs/WAVE-1-EXIT.md](docs/WAVE-1-EXIT.md). Docs index: [docs/README.md](docs/README.md).

## Shipped (Wave 1)

- Hierarchy: Epic → Project → Section → Task → subtask → nested subtask
- Smart views: Inbox, Today, Upcoming, Project, Label
- Calendar day/week, due markers, manual scheduled blocks
- Quick-add, search, undo, optimistic UI, keyboard shortcuts
- Labels + color presets; nine UI themes (Settings)
- Local Docker Compose + Postgres; bootstrap user (no login wall)

## Quick start (Docker Compose)

Requires [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or any OCI-compatible runtime).

```powershell
docker compose -f infra/compose/compose.yaml up --build
```

| Service | URL |
|---------|-----|
| Web (Compose production build) | http://localhost:8080 |
| API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Postgres | `localhost:5432` (user/db/password: `theplan`) |

Stop: `docker compose -f infra/compose/compose.yaml down`

### Backup one-liner

```powershell
docker compose -f infra/compose/compose.yaml exec -T postgres pg_dump -U theplan theplan > theplan-backup.sql
```

## Local development (without full Compose)

### 1. PostgreSQL

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

Open http://localhost:5173 (Vite dev). Compose serves the production build on **:8080**.

## Repository layout

```
apps/api/          FastAPI + SQLAlchemy 2 + Alembic
apps/web/          Vite + React + TypeScript
infra/compose/     Docker Compose stack
docs/              Product docs, ADRs, baseline SQL, Wave 1 exit
```
