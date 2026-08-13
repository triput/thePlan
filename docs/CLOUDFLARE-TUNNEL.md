# Cloudflare Tunnel (remote access)

Expose thePlan’s **web** service (port 80 inside Compose → same-origin `/api` proxy) through a Cloudflare Tunnel. Do **not** publish Postgres or pgAdmin through the tunnel.

## Prerequisites

- Working local stack: `docker compose -f infra/compose/compose.yaml up -d`
- A [Cloudflare](https://www.cloudflare.com/) account with a domain on Cloudflare DNS
- [Zero Trust](https://one.dash.cloudflare.com/) access (free tier is enough for a personal tunnel)

## 1. Create the tunnel

1. Open **Zero Trust** → **Networks** → **Tunnels** → **Create a tunnel**.
2. Choose **Cloudflared**, name it (e.g. `theplan-home`).
3. Copy the **connector token** (starts with `eyJ…`). Keep it private.
4. Under **Public Hostname**:
   - Subdomain + domain (e.g. `plan.example.com`)
   - Type: **HTTP**
   - URL: **`http://web:80`** (Compose service name + container port)

Save. Cloudflare will create the DNS CNAME for you.

## 2. Store the token locally

Create `infra/compose/.env` (gitignored via root `.env` / `.env.*` rules):

```env
CLOUDFLARE_TUNNEL_TOKEN=eyJ...your-token...
```

Never commit this file. If you must rotate credentials after a leak, revoke the tunnel connector in Zero Trust and issue a new token.

## 3. Start cloudflared

From the repo root:

```powershell
docker compose -f infra/compose/compose.yaml --profile tunnel up -d
```

`cloudflared` joins the Compose network, reads `TUNNEL_TOKEN`, and proxies the public hostname to `web:80`. Session cookies stay same-origin on that hostname (same pattern as localhost:8080).

Compose pins **`cloudflare/cloudflared:2026.7.3`** (see [HYGIENE-W3.md](./HYGIENE-W3.md)). Bump that tag deliberately when upgrading.

Check:

```powershell
docker compose -f infra/compose/compose.yaml --profile tunnel ps
docker compose -f infra/compose/compose.yaml logs -f cloudflared
```

Stop the connector only:

```powershell
docker compose -f infra/compose/compose.yaml --profile tunnel stop cloudflared
```

## 4. HTTPS cookies (production)

Browsers treat the tunneled hostname as HTTPS. For reliable sessions remotely, set on the **api** service:

```env
SESSION_HTTPS_ONLY=true
```

(Wire via Compose `environment` / `.env` when you harden beyond local dev defaults. Local http://localhost:8080 should keep `SESSION_HTTPS_ONLY=false`.)

Also set a strong `SESSION_SECRET` before exposing the app beyond your LAN.

If the public hostname differs from localhost, add it to the API `CORS_ORIGINS` JSON list (Compose `api.environment`) so browser clients that talk cross-origin still work. Prefer same-origin via the web proxy (`VITE_API_URL=""`) so CORS stays irrelevant for the main UI.

## 5. Optional: Cloudflare Access

Access adds an identity gate **in front of** thePlan (in addition to app login):

1. Zero Trust → **Access** → **Applications** → **Add an application** → **Self-hosted**.
2. Application domain: the same public hostname (e.g. `plan.example.com`).
3. Policy: allow your email(s) or an IdP group (email one-time PIN is fine for a household).
4. Save. Visitors hit Access first, then thePlan’s own sign-in.

Access is recommended for anything reachable on the public internet; app passwords alone are not a substitute for edge auth when the host is exposed.

## What not to expose

| Service | Tunnel? |
|---------|---------|
| `web` (:80) | Yes — this is the app |
| `api` (:8000) | No — use `/api` via web |
| `postgres` | No |
| `pgadmin` | No — keep on LAN / VPN only |

## Related

- [USER-GUIDE.md](./USER-GUIDE.md) — day-to-day app use
- [README.md](../README.md) — Compose quick start + backups
- [ADR-003](./adr/ADR-003-local-first-auth.md) — local-first auth progression
