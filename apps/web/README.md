# thePlan Web

Vite + React + TypeScript frontend shell.

## Local development

```powershell
cd apps/web
npm install
copy .env.example .env
npm run dev
```

Open http://localhost:5173 — Vite proxies `/api` to the API on port 8000. Docker Compose serves the production build at http://localhost:8080 (nginx also proxies `/api`).

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | _(empty)_ | Leave empty for same-origin `/api` (required for session cookies). Absolute URL only for special cases. |

## Docker

Production-style image serves static build via nginx — see `infra/compose/compose.yaml`.
