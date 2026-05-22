# TeamsLike API — Deployment Handoff

This document is the operator-facing summary. Source of truth for compose files
and Caddyfile is `infra/`. Read `infra/README.md` for the deployment order
across the three stacks (api / chatwoot / jitsi).

---

## Architecture at a glance

```
                              ┌──────────────────────┐
                              │  Caddy (in api stack)│
                              │  ports: 80, 443      │
                              └─────────┬────────────┘
                                        │ teamslike_edge network
              ┌─────────────────────────┼─────────────────────────┐
              │                         │                         │
      api.teamslike.com         support.teamslike.com      meet.teamslike.com
              │                         │                         │
        ┌─────▼─────┐             ┌─────▼─────┐             ┌─────▼─────┐
        │   api     │             │  rails    │             │   web     │
        │ (FastAPI) │             │ (Chatwoot)│             │  (Jitsi)  │
        └───────────┘             └───────────┘             └───────────┘
              │                         │                         │
      ┌───────┴────────┐         ┌──────┴──────┐          ┌───────┴───────┐
      │ postgres + redis│        │ chatwoot-pg │          │ prosody +     │
      │ (api-internal)  │        │ + chatwoot- │          │ jicofo + jvb  │
      └─────────────────┘        │   redis     │          │ (jitsi-int.)  │
                                 └─────────────┘          └───────────────┘
                                                                 │
                                                          UDP 10000 (media)
```

Each stack has its own Postgres + Redis. Do not cross them.

---

## Network ports

| Host port | Protocol | Service | Purpose |
|-----------|----------|---------|---------|
| 80 | TCP | Caddy | HTTP → 301 to HTTPS |
| 443 | TCP | Caddy | HTTPS (api / chatwoot / jitsi) |
| 10000 | UDP | jvb (Jitsi) | WebRTC media — must be public-reachable |

Postgres, Redis, and internal app containers do **not** bind host ports.
Firewall should expose only 22 (ssh), 80, 443, 10000/udp.

---

## DNS

All three subdomains must resolve to this server before deploy (Caddy obtains
Let's Encrypt certs on first request — failed cert attempts get rate-limited).

| Record | Type | Value |
|--------|------|-------|
| `api.teamslike.com` | A | server IP |
| `support.teamslike.com` | A | server IP |
| `meet.teamslike.com` | A | server IP |

---

## Environment variables (API)

Full template: `infra/.env.prod.example`. Required vars marked **R**, optional **O**.

| Var | R/O | Notes |
|-----|-----|-------|
| `APP_ENV` | O | Free-form (`production`, `staging`). Default `development`. |
| `APP_DEBUG` | O | `false` in prod. Reveals stack traces if `true`. |
| `APP_PORT` | O | Default `8800`. Container-internal only. |
| `CORS_ALLOWED_ORIGINS` | O | Comma-separated origins. Empty = no CORS. |
| `DATABASE_URL` | **R** | `postgresql+asyncpg://...`. **Driver prefix is mandatory.** |
| `DATABASE_ECHO` | O | `true` logs SQL — keep `false` in prod. |
| `REDIS_URL` | **R** | `redis://:password@host:6379/0` |
| `REDIS_KEY_PREFIX` | O | Default `teamslike`. |
| `JWT_SECRET_KEY` | **R** | Generate with `openssl rand -hex 64`. **Rotating it invalidates all sessions.** |
| `JWT_ALGORITHM` | O | Default `HS256`. |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | O | Default `60`. |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | O | Default `14`. |
| `JITSI_PUBLIC_URL` | **R** | `https://meet.teamslike.com` |
| `JITSI_DOMAIN` | O | Default `meet.jitsi`. |
| `JITSI_JWT_APP_ID` | **R** | **Must match `JWT_APP_ID` in `infra/jitsi/.env`.** |
| `JITSI_JWT_APP_SECRET` | **R** | **Must match `JWT_APP_SECRET` in `infra/jitsi/.env`.** |
| `JITSI_JWT_ALGORITHM` | O | Default `HS256`. |
| `JITSI_JWT_TOKEN_TTL_MINUTES` | O | Default `120`. |
| `CHATWOOT_BASE_URL` | **R** | `https://support.teamslike.com` |
| `CHATWOOT_USER_API_TOKEN` | **R** | Obtained after first Chatwoot login (Profile → Access Token). |
| `CHATWOOT_ACCOUNT_ID` | O | Default `1`. |
| `GUNICORN_WORKERS` | O | Default `2`. Recommended: `2 * cores + 1`. |
| `GUNICORN_TIMEOUT` | O | Default `60` seconds. |
| `LOG_FORMAT` | O | `json` (default) or `text`. JSON is recommended for production. |
| `LOG_LEVEL` | O | `INFO` (default), `WARNING`, `ERROR`, `DEBUG`. |
| `SENTRY_DSN` | O | Empty = Sentry disabled. Set to enable error tracking. |
| `SENTRY_ENVIRONMENT` | O | Default `production`. |
| `SENTRY_TRACES_SAMPLE_RATE` | O | `0.0` – `1.0`. Default `0.0` (errors only). |
| `RUN_MIGRATIONS_ON_START` | O | `0` (default). Compose runs migrations as a separate one-shot service. |

---

## Health endpoints

The API exposes two distinct probes — use them correctly:

| Path | Purpose | Behavior | Suggested probe |
|------|---------|----------|-----------------|
| `/health` | **Liveness** — is the process up? | Always returns 200 if gunicorn is responsive. Does not touch DB/Redis. | Container HEALTHCHECK / liveness probe |
| `/ready` | **Readiness** — can it serve traffic? | Probes Postgres (`SELECT 1`) and Redis (`PING`). Returns 503 if either fails. | Load balancer readiness probe |

Sample `/ready` body:
```json
{ "status": "ready", "checks": { "database": "ok", "redis": "ok" } }
```

Failure:
```json
{ "status": "not_ready", "checks": { "database": "error: OperationalError", "redis": "ok" } }
```

---

## Deployment procedure

### First-time

```bash
# 1. clone + checkout target commit
git clone <repo> teamslike && cd teamslike && git checkout <sha>

# 2. create env files from templates
cp infra/.env.prod.example       infra/.env.prod
cp infra/chatwoot/.env.example   infra/chatwoot/.env
cp infra/jitsi/.env.example      infra/jitsi/.env
# ... edit each, fill secrets ...

# 3. bring up API stack (creates teamslike_edge network, runs migrations)
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml up -d --build

# 4. smoke test
scripts/smoke.sh https://api.teamslike.com

# 5. bring up Chatwoot
docker compose --env-file infra/chatwoot/.env -f infra/chatwoot/docker-compose.yml \
  run --rm rails bundle exec rails db:chatwoot_prepare
docker compose --env-file infra/chatwoot/.env -f infra/chatwoot/docker-compose.yml up -d
# Then: create admin user in UI, copy access token into infra/.env.prod, restart API.

# 6. bring up Jitsi
docker compose --env-file infra/jitsi/.env -f infra/jitsi/docker-compose.yml up -d
```

### Subsequent deploys (API only)

```bash
git pull
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml build api migrate
# Migrations run BEFORE rolling new code:
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml run --rm migrate
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml up -d api
scripts/smoke.sh https://api.teamslike.com
```

Gunicorn workers will be replaced gracefully; in-flight requests have
`GUNICORN_GRACEFUL_TIMEOUT` (default 30s) to finish.

### Rollback

```bash
git checkout <previous-sha>
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml build api
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml up -d api
```

**Warning:** rolling back across a migration that altered/dropped columns
requires a separate down-migration plan. Forward-only migrations are safer —
prefer additive changes.

---

## Logging

Default format is JSON (`LOG_FORMAT=json`). Sample line:

```json
{"ts":"2026-05-22T11:54:35.123+00:00","level":"INFO","logger":"uvicorn.access","msg":"172.24.0.5:40022 - \"GET /health HTTP/1.1\" 200"}
```

Switch to plain text for local debugging only: `LOG_FORMAT=text`.

All app + uvicorn + gunicorn logs go to stdout. Capture via `docker logs` or
forward via Docker logging driver (json-file/journald/Loki/etc.) — that
decision is yours.

---

## Backups (recommendations, not implemented)

| Asset | Approach |
|-------|----------|
| API Postgres | `pg_dump` daily → object storage (S3/R2). Retain 30 days minimum. |
| Chatwoot Postgres | Same. Chatwoot DB carries customer conversations — back this up religiously. |
| Chatwoot uploads | `chatwoot_storage` volume — daily snapshot or switch `ACTIVE_STORAGE_SERVICE=amazon`. |
| Caddy data | `caddy_data` volume holds ACME certs. Loss → cert re-issue (rate-limited). Worth snapshotting. |
| Jitsi config | `${CONFIG}` host dir contains generated XMPP secrets. Snapshot once after first start. |
| Redis | Cache only (JWT denylist, rate limit counters). Loss is tolerable. |

Test restore quarterly.

---

## Known operational caveats

1. **Migration race:** API service `depends_on: migrate (service_completed_successfully)`. Compose enforces this — do not bypass.
2. **JWT secret rotation:** rotating `JWT_SECRET_KEY` invalidates every issued token immediately. Schedule rotations during a maintenance window.
3. **CORS:** `CORS_ALLOWED_ORIGINS=""` means **no cross-origin requests**. Browsers will block your frontend if the origin isn't listed.
4. **First Chatwoot deploy is two-step:** API needs a Chatwoot access token, which only exists after a human creates an account. There's no way to bootstrap this from compose. Plan for a brief gap.
5. **Jitsi UDP 10000:** without this open, the call connects but no video flows. Common silent failure — verify with a 2-person test call after deploy.
6. **TLS rate limit:** Let's Encrypt issues 5 certs per domain per week. If DNS isn't ready and Caddy retries, you'll burn the quota. Bring up DNS first.

---

## Files / paths

| Path | Purpose |
|------|---------|
| `infra/Dockerfile` | API image build |
| `infra/docker-entrypoint.sh` | Container entry; `migrate` and `serve` modes |
| `infra/docker-compose.prod.yml` | API + Postgres + Redis + Caddy |
| `infra/chatwoot/docker-compose.yml` | Chatwoot stack |
| `infra/jitsi/docker-compose.yml` | Jitsi stack |
| `infra/caddy/Caddyfile` | Reverse proxy config (3 domains) |
| `infra/.env.prod.example` | API env template |
| `infra/chatwoot/.env.example` | Chatwoot env template |
| `infra/jitsi/.env.example` | Jitsi env template |
| `scripts/smoke.sh` | Post-deploy health verification |
| `alembic/versions/` | DB migrations (forward-only style) |
