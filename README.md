# thePlan

Personal web-first task + scheduling app alongside the Synesis/Phronesis suite.

**Wave 1 (MVP) exited 2026-08-10.** W1.5 closeout + W1.6 mobile shipped. **Next:** Google Calendar → Scheduler — [docs/07-wave-roadmap.md](docs/07-wave-roadmap.md). Exit record: [docs/WAVE-1-EXIT.md](docs/WAVE-1-EXIT.md). Docs index: [docs/README.md](docs/README.md). **Using the app:** [docs/USER-GUIDE.md](docs/USER-GUIDE.md).

## Shipped (Wave 1)

- Hierarchy: Epic → Project → Section → Task → subtask → nested subtask
- Smart views: Inbox, Today, Upcoming, Project, Label, Epic rollup
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
| pgAdmin (optional) | http://localhost:5050 — `admin@example.com` / `theplan` |

pgAdmin is behind Compose profile `tools` (not started by default):

```powershell
docker compose -f infra/compose/compose.yaml --profile tools up -d pgadmin
```

Preloaded server **thePlan** → host `postgres`, DB password `theplan`.

Stop: `docker compose -f infra/compose/compose.yaml --profile tools down`

### Backup one-liner

```powershell
docker compose -f infra/compose/compose.yaml exec -T postgres pg_dump -U theplan theplan > theplan-backup.sql
```

### Scheduled backups

Scripts write timestamped dumps to gitignored `backups/` and prune files older than **14** days (`BACKUP_KEEP_DAYS`).

```powershell
# Windows — run once
.\scripts\backup-postgres.ps1

# Schedule daily at 02:00 (adjust path):
schtasks /Create /TN "thePlan Postgres Backup" /TR "powershell -NoProfile -File `"F:\Code Repo\ThePlan\scripts\backup-postgres.ps1`"" /SC DAILY /ST 02:00
```

```bash
# Linux/macOS — run once
chmod +x scripts/backup-postgres.sh
./scripts/backup-postgres.sh

# cron example (daily 02:15):
# 15 2 * * * /path/to/ThePlan/scripts/backup-postgres.sh >> /path/to/ThePlan/backups/backup.log 2>&1
```

### Cloudflare Tunnel (remote access)

Optional Compose profile `tunnel` runs `cloudflared` to the **web** service. Setup: [docs/CLOUDFLARE-TUNNEL.md](docs/CLOUDFLARE-TUNNEL.md).

```powershell
# Put CLOUDFLARE_TUNNEL_TOKEN in infra/compose/.env (see infra/compose/.env.example)
docker compose -f infra/compose/compose.yaml --profile tunnel up -d
```

## Local development (without full Compose)

### 1. PostgreSQL

```powershell
docker compose -f infra/compose/compose.yaml up postgres -d
```

### 2. API

```powershell
cd apps/api
py -3.14 -m venv .venv
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
infra/compose/     Docker Compose stack (+ optional tunnel / pgAdmin profiles)
scripts/           Operator helpers (scheduled Postgres backup)
docs/              Product docs, ADRs, baseline SQL, Wave 1 exit
```
