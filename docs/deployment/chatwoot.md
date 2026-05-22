# Chatwoot — Deployment

Self-hosted customer support platform. Owns its own Postgres + Redis (separate
from the API stack). Joins the shared `teamslike_edge` network so Caddy (in
the API stack) can proxy `support.teamslike.com` to it.

Compose: `infra/chatwoot/docker-compose.yml`
Env template: `infra/chatwoot/.env.example`

---

## Why a separate stack?

- Chatwoot has its own schema, migration cadence, and Sidekiq worker.
- Its DB carries customer conversations — a different backup/retention policy than the API DB.
- Upgrading Chatwoot must not affect the API and vice versa.

---

## Stack components

| Service | Image | Internal port | Purpose |
|---|---|---|---|
| `chatwoot-postgres` | `postgres:16-alpine` | 5432 | Chatwoot DB |
| `chatwoot-redis` | `redis:7-alpine` | 6379 | Sidekiq queue + ActionCable |
| `rails` | `chatwoot/chatwoot:vX.Y.Z` | 3000 | Web + API + ActionCable (WebSocket) |
| `sidekiq` | same | — | Background jobs (mailers, webhooks, etc.) |

None of these bind host ports — Caddy reaches `rails:3000` via `teamslike_edge`.

---

## Environment variables

Full template: `infra/chatwoot/.env.example`. **R** = required, **O** = optional.

### Core
| Var | R/O | Notes |
|---|---|---|
| `CHATWOOT_IMAGE` | **R** | Pin a specific Chatwoot version, e.g. `chatwoot/chatwoot:v4.4.0`. |
| `FRONTEND_URL` | **R** | `https://support.teamslike.com` — must match the public URL Caddy serves. |
| `INSTALLATION_NAME` | O | Shown in UI. |
| `DEFAULT_LOCALE` | O | `tr`, `en`, etc. |
| `SECRET_KEY_BASE` | **R** | `openssl rand -hex 64`. Rotating it invalidates sessions and cookies. |
| `RAILS_ENV` | **R** | `production`. |
| `RAILS_LOG_TO_STDOUT` | O | `true` (recommended). |
| `RAILS_MAX_THREADS` | O | Default `5`. |
| `FORCE_SSL` | O | `true` — Chatwoot will only emit HTTPS URLs. |
| `ENABLE_ACCOUNT_SIGNUP` | O | `false` — only admins create accounts. |

### Database
| Var | R/O | Notes |
|---|---|---|
| `POSTGRES_HOST` | **R** | `chatwoot-postgres` (compose service name). |
| `POSTGRES_PORT` | O | `5432`. |
| `POSTGRES_DATABASE` | **R** | `chatwoot`. |
| `POSTGRES_USERNAME` | **R** | `chatwoot`. |
| `POSTGRES_PASSWORD` | **R** | Strong random secret. |

### Redis
| Var | R/O | Notes |
|---|---|---|
| `REDIS_URL` | **R** | `redis://:password@chatwoot-redis:6379` |
| `REDIS_PASSWORD` | **R** | Must match the password embedded in `REDIS_URL`. |

### Mailer (required for password resets, notifications)
| Var | R/O | Notes |
|---|---|---|
| `MAILER_SENDER_EMAIL` | **R** | `Chatwoot <support@teamslike.com>` |
| `SMTP_ADDRESS` | **R** | Your SMTP host. |
| `SMTP_PORT` | **R** | `587` for STARTTLS. |
| `SMTP_DOMAIN` | **R** | Your domain. |
| `SMTP_USERNAME` | **R** | SMTP auth user. |
| `SMTP_PASSWORD` | **R** | SMTP auth password. |
| `SMTP_AUTHENTICATION` | O | `plain` (default for most providers). |
| `SMTP_ENABLE_STARTTLS_AUTO` | O | `true`. |

### File storage
| Var | R/O | Notes |
|---|---|---|
| `ACTIVE_STORAGE_SERVICE` | O | `local` (default — uses `chatwoot_storage` volume) or `amazon` (S3-compatible). |

For S3-compatible storage add `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`,
`AWS_REGION`, `S3_BUCKET_NAME`. R2/MinIO also work via these.

---

## First-time deploy

Prerequisite: the API stack must be up so that `teamslike_edge` network exists.

```bash
cp infra/chatwoot/.env.example infra/chatwoot/.env
# ... edit, fill secrets ...

# 1. Prepare the schema (run-and-exit)
docker compose --env-file infra/chatwoot/.env \
  -f infra/chatwoot/docker-compose.yml \
  run --rm rails bundle exec rails db:chatwoot_prepare

# 2. Start the stack
docker compose --env-file infra/chatwoot/.env \
  -f infra/chatwoot/docker-compose.yml up -d

# 3. Verify via Caddy (after DNS is live)
curl -fsS https://support.teamslike.com/api -o /dev/null && echo OK
```

---

## Bootstrap the API integration (two-step)

The TeamsLike API needs a Chatwoot **user API token** to talk to Chatwoot.
This token only exists after a human creates the first admin account — there
is no way to bootstrap it from compose.

Steps:

1. Open `https://support.teamslike.com` in a browser.
2. Sign up as the first user → automatically becomes super admin.
3. Profile → **Access Token** → copy the value.
4. Set it in the API env: `infra/.env.prod` → `CHATWOOT_USER_API_TOKEN=...`
5. Restart the API: `docker compose -f infra/docker-compose.prod.yml restart api`

Plan for a brief gap between Chatwoot deploy and API restart.

---

## Subsequent upgrades

```bash
# Bump CHATWOOT_IMAGE in infra/chatwoot/.env, then:
docker compose --env-file infra/chatwoot/.env \
  -f infra/chatwoot/docker-compose.yml pull
# Run schema migrations
docker compose --env-file infra/chatwoot/.env \
  -f infra/chatwoot/docker-compose.yml \
  run --rm rails bundle exec rails db:chatwoot_prepare
# Roll new code
docker compose --env-file infra/chatwoot/.env \
  -f infra/chatwoot/docker-compose.yml up -d
```

Always read the Chatwoot release notes between major versions. They
occasionally require config changes or one-off data migrations.

---

## Backup

| Asset | Recommendation |
|---|---|
| `chatwoot_postgres_data` | `pg_dump` **daily**. Carries customer conversations — non-negotiable. |
| `chatwoot_storage` | Daily snapshot of the volume, or migrate to S3 (`ACTIVE_STORAGE_SERVICE=amazon`) and let S3 versioning handle it. |
| `chatwoot_redis_data` | Optional — only Sidekiq job state. Loss results in dropped/retried jobs. |

Test restore quarterly.

---

## Common ops

| Task | Command |
|---|---|
| View logs (rails + sidekiq) | `docker compose -f infra/chatwoot/docker-compose.yml logs -f` |
| Restart rails only | `docker compose -f infra/chatwoot/docker-compose.yml restart rails` |
| Rails console | `docker compose -f infra/chatwoot/docker-compose.yml exec rails bundle exec rails console` |
| Sidekiq queue stats | `docker compose -f infra/chatwoot/docker-compose.yml exec sidekiq bundle exec sidekiq stats` (or via UI: `/sidekiq` while logged in as super admin) |
| psql into the Chatwoot DB | `docker compose -f infra/chatwoot/docker-compose.yml exec chatwoot-postgres psql -U chatwoot` |

---

## Caveats

1. **Lisans:** Chatwoot uses the Chatwoot Custom License (restricts SaaS resale). Self-hosting for internal customer support is fine — review `LICENSE` once.
2. **First-deploy gap:** API will log Chatwoot HTTP errors until the access token is set. Expected behavior — see bootstrap section.
3. **Mailer is required.** Password reset, agent invites, and customer notifications all need working SMTP. Test with a real address right after deploy.
4. **WebSocket (ActionCable):** ActionCable runs on `/cable` over the same port. Caddy's `reverse_proxy` handles WS upgrade automatically.
5. **`FORCE_SSL=true` requires HTTPS upstream.** If Caddy isn't fronting it yet, Chatwoot redirects break. Bring Caddy + DNS up first.
