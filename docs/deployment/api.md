# API — Deployment

The TeamsLike FastAPI service. Owns Postgres (its own), Redis (its own), and
the Caddy reverse proxy that fronts all three subdomains.

Compose: `infra/docker-compose.prod.yml`
Image: `infra/Dockerfile`
Env template: `infra/.env.prod.example`

---

## Stack components

| Service | Image | Internal port | Host port | Purpose |
|---|---|---|---|---|
| `postgres` | `postgres:16-alpine` | 5432 | — | API database |
| `redis` | `redis:7-alpine` | 6379 | — | Cache, JWT denylist, rate limits |
| `migrate` | `teamslike-api` | — | — | One-shot Alembic upgrade |
| `api` | `teamslike-api` | 8800 | — | FastAPI + Gunicorn (uvicorn workers) |
| `caddy` | `caddy:2-alpine` | — | 80, 443 | TLS termination for all three domains |

Postgres + Redis are not exposed on the host. Only Caddy binds host ports.

---

## Environment variables

Full template in `infra/.env.prod.example`. **R** = required, **O** = optional.

### App
| Var | R/O | Notes |
|---|---|---|
| `APP_ENV` | O | Free-form (`production`, `staging`). Default `development`. |
| `APP_DEBUG` | O | `false` in prod — `true` reveals stack traces. |
| `APP_PORT` | O | Default `8800` (container-internal). |
| `CORS_ALLOWED_ORIGINS` | O | Comma-separated origins. Empty = no CORS. |

### Database / cache
| Var | R/O | Notes |
|---|---|---|
| `DATABASE_URL` | **R** | `postgresql+asyncpg://...` — driver prefix mandatory. |
| `DATABASE_ECHO` | O | `true` logs every SQL. Keep `false` in prod. |
| `REDIS_URL` | **R** | `redis://:password@host:6379/0` |
| `REDIS_KEY_PREFIX` | O | Default `teamslike`. |

### JWT (API auth)
| Var | R/O | Notes |
|---|---|---|
| `JWT_SECRET_KEY` | **R** | `openssl rand -hex 64`. **Rotating it invalidates all sessions.** |
| `JWT_ALGORITHM` | O | Default `HS256`. |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | O | Default `60`. |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | O | Default `14`. |

### Cross-stack integration
| Var | R/O | Notes |
|---|---|---|
| `JITSI_PUBLIC_URL` | **R** | `https://meet.teamslike.com` |
| `JITSI_JWT_APP_ID` | **R** | **Must match `JWT_APP_ID` in Jitsi `.env`.** |
| `JITSI_JWT_APP_SECRET` | **R** | **Must match `JWT_APP_SECRET` in Jitsi `.env`.** |
| `JITSI_JWT_ALGORITHM` | O | Default `HS256`. |
| `JITSI_JWT_TOKEN_TTL_MINUTES` | O | Default `120`. |
| `CHATWOOT_BASE_URL` | **R** | `https://support.teamslike.com` |
| `CHATWOOT_USER_API_TOKEN` | **R** | Obtained from Chatwoot UI after first admin login. |
| `CHATWOOT_ACCOUNT_ID` | O | Default `1`. |

### Runtime
| Var | R/O | Notes |
|---|---|---|
| `GUNICORN_WORKERS` | O | Default `2`. Recommended: `2 * cores + 1`. |
| `GUNICORN_TIMEOUT` | O | Default `60` seconds. |
| `GUNICORN_GRACEFUL_TIMEOUT` | O | Default `30` seconds. |
| `LOG_FORMAT` | O | `json` (default) or `text`. |
| `LOG_LEVEL` | O | `INFO` (default), `WARNING`, `ERROR`, `DEBUG`. |
| `SENTRY_DSN` | O | Empty = Sentry disabled. |
| `SENTRY_ENVIRONMENT` | O | Default `production`. |
| `SENTRY_TRACES_SAMPLE_RATE` | O | `0.0` – `1.0`. Default `0.0` (errors only, no perf traces). |
| `RUN_MIGRATIONS_ON_START` | O | `0` (default). Compose runs migrations via a separate one-shot service — do not flip this on. |

### Deploy (Caddy)
| Var | R/O | Notes |
|---|---|---|
| `API_DOMAIN` | **R** | Public API hostname. Must have an A record on this server. |
| `CHATWOOT_DOMAIN` | O | If Chatwoot is deployed — needed for Caddy to route `support.*`. |
| `JITSI_DOMAIN` | O | If Jitsi is deployed — needed for Caddy to route `meet.*`. |
| `ACME_EMAIL` | **R** | Let's Encrypt cert expiry notification email. |
| `API_IMAGE` | O | Override to pull a prebuilt image (e.g. `ghcr.io/...:sha-xxxx`). Default `teamslike-api:latest`. |

---

## Health endpoints

| Path | Purpose | Behavior | Probe as |
|---|---|---|---|
| `/health` | Liveness | Always 200 if process is up. No DB/Redis touch. | Container HEALTHCHECK |
| `/ready` | Readiness | Probes Postgres (`SELECT 1`) and Redis (`PING`). 503 if either fails. | Load balancer readiness |

`/ready` response:
```json
{ "status": "ready", "checks": { "database": "ok", "redis": "ok" } }
```

Failure mode:
```json
{ "status": "not_ready", "checks": { "database": "ok", "redis": "error: ConnectionError" } }
```

---

## First-time deploy

```bash
cp infra/.env.prod.example infra/.env.prod
# ... edit infra/.env.prod, fill secrets ...

docker compose --env-file infra/.env.prod \
  -f infra/docker-compose.prod.yml up -d --build

scripts/smoke.sh https://api.teamslike.com
```

The compose dependency chain enforces:
`postgres healthy → redis healthy → migrate completes → api starts → caddy starts`

---

## Subsequent deploy

```bash
git pull
docker compose --env-file infra/.env.prod \
  -f infra/docker-compose.prod.yml build api migrate

# Run migrations BEFORE rolling new code:
docker compose --env-file infra/.env.prod \
  -f infra/docker-compose.prod.yml run --rm migrate

# Roll new code (gunicorn graceful reload — in-flight requests get GUNICORN_GRACEFUL_TIMEOUT)
docker compose --env-file infra/.env.prod \
  -f infra/docker-compose.prod.yml up -d api

scripts/smoke.sh https://api.teamslike.com
```

---

## Rollback

```bash
git checkout <previous-sha>
docker compose --env-file infra/.env.prod \
  -f infra/docker-compose.prod.yml build api
docker compose --env-file infra/.env.prod \
  -f infra/docker-compose.prod.yml up -d api
```

**Caveat:** rolling back across a migration that altered/dropped columns
requires a separate down-migration plan. Prefer forward-only, additive
migrations — they're safer to roll back.

---

## Logging

Default: structured JSON to stdout.

```json
{"ts":"2026-05-22T12:15:32.956+00:00","level":"INFO","logger":"uvicorn.access","msg":"172.24.0.5:35744 - \"GET /ready HTTP/1.1\" 200"}
```

Set `LOG_FORMAT=text` for human-readable local debugging.

Capture via `docker logs` or any Docker logging driver — that's an ops choice.

---

## Sentry (optional)

Set `SENTRY_DSN` to enable. Empty = no-op (Sentry SDK is loaded conditionally).

Defaults: errors only (`SENTRY_TRACES_SAMPLE_RATE=0.0`), no PII
(`send_default_pii=False`).

---

## Backup

| Asset | Recommendation |
|---|---|
| Postgres | `pg_dump teamslike` daily → object storage. Retain 30 days. |
| Redis | Optional. Cache contents are rebuildable; only JWT denylist + rate-limit counters are stored. |
| Caddy data | `caddy_data` volume — holds Let's Encrypt certs. Loss → cert re-issue (rate-limited). Worth snapshotting. |

---

## Common ops

| Task | Command |
|---|---|
| View API logs | `docker compose -f infra/docker-compose.prod.yml logs -f api` |
| Restart API only | `docker compose -f infra/docker-compose.prod.yml restart api` |
| Run a shell in the API container | `docker compose -f infra/docker-compose.prod.yml exec api sh` |
| Manual migration | `docker compose -f infra/docker-compose.prod.yml run --rm migrate` |
| psql into the DB | `docker compose -f infra/docker-compose.prod.yml exec postgres psql -U teamslike` |

---

## Caveats

1. **JWT secret rotation** invalidates every token immediately. Schedule rotations in a maintenance window.
2. **CORS empty = no cross-origin requests.** Browsers will block your frontend if its origin isn't listed.
3. **Migration race:** `api` depends on `migrate` completing — do not bypass.
4. **TLS rate limit:** Let's Encrypt issues 5 certs per domain per week. Bring DNS up before Caddy.
