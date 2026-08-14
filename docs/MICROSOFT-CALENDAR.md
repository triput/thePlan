# Microsoft Calendar — Entra app setup (operator)

W3 Slice 2 **shipped** ([ADR-008](./adr/ADR-008-microsoft-calendar.md)). Secrets stay in gitignored Compose `.env` / `.secrets-backup/` — never commit.

## 1. Register an app

1. [Microsoft Entra admin center](https://entra.microsoft.com/) → **App registrations** → **New registration**.
2. Name e.g. `thePlan Calendar`.
3. Supported account types: **Accounts in any organizational directory and personal Microsoft accounts** (maps to tenant `common`).
4. Redirect URI — **Web**:  
   - Local: `http://localhost:8000/api/v1/calendar/oauth/microsoft/callback`  
   - Tunnel: `https://plan.silverhelmet.com/api/v1/calendar/oauth/microsoft/callback`

## 2. Client secret

**Certificates & secrets** → **New client secret**. Copy the **Value** once into Compose env as `MICROSOFT_CLIENT_SECRET`.

## 3. API permissions

**API permissions** → Microsoft Graph → **Delegated**:

- `Calendars.ReadWrite`
- `offline_access`
- `User.Read`

Grant admin consent if your tenant requires it (personal accounts usually consent at login).

## 4. Compose env

```env
MICROSOFT_CLIENT_ID=<Application (client) ID>
MICROSOFT_CLIENT_SECRET=<secret value>
MICROSOFT_REDIRECT_URI=https://plan.silverhelmet.com/api/v1/calendar/oauth/microsoft/callback
MICROSOFT_TENANT_ID=common
TOKEN_ENCRYPTION_KEY=<same Fernet key as Google>
FRONTEND_ORIGIN=https://plan.silverhelmet.com
```

Pass through `infra/compose/compose.yaml` api `environment` (mirror Google vars). Restart api after editing `.env`.

## 5. Connect in the app

Settings → **Microsoft Calendar** → Connect. After consent, pick calendars, mark one **primary**, optional **Push time blocks**.
