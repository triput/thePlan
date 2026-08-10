# thePlan Web

Vite + React + TypeScript frontend shell.

## Local development

```powershell
cd apps/web
npm install
copy .env.example .env
npm run dev
```

Open http://localhost:5173 — requires the API running on port 8000 (see `apps/api/README.md` or Docker Compose).

## Environment

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `http://localhost:8000` | Backend base URL |

## Docker

Production-style image serves static build via nginx — see `infra/compose/compose.yaml`.
