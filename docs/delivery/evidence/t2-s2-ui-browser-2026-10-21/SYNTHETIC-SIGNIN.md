# Synthetic sign-in (Dex IAB / Jim browser) — Nebula only

**Stack (keep up for Dex focused UI check):**

| Layer | URL / DSN |
| --- | --- |
| Web | `http://127.0.0.1:5173` (Vite proxies `/api` → API) |
| API | `http://127.0.0.1:8000` |
| DB | Postgres `theplan_s1_test` @ `127.0.0.1:5433` |

**Credentials (local file only — do not paste into Slack):**

`F:\Code Repo\ThePlan\.secrets-backup\nebula-credentials.txt`

Format: `username` / `email` / `password` lines. Path is **gitignored** (`.secrets-backup/`). Demo Nebula is disposable synthetic household seed — **not** production / shared household tokens.

**Sign-in:** open Vite URL → Sign in → identifier `nebula@localhost` (or username from file) → passphrase from that file.

If the file is missing, recreate via API lifespan with `SEED_DEMO_USER=true` and optional `DEMO_NEBULA_PASSWORD`, or ask Jim — do not invent household passwords.
