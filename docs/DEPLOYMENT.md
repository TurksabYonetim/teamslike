# Deployment — Overview

TeamsLike runs as three independent compose stacks behind a single Caddy
reverse proxy. Each stack has its own database. Each one has its own dedicated
deployment doc — start there for stack-specific details.

| Stack | Doc | Compose file | Public domain |
|---|---|---|---|
| **API** (FastAPI) | [api.md](deployment/api.md) | `infra/docker-compose.prod.yml` | `api.teamslike.com` |
| **Chatwoot** | [chatwoot.md](deployment/chatwoot.md) | `infra/chatwoot/docker-compose.yml` | `support.teamslike.com` |
| **Jitsi Meet** | [jitsi.md](deployment/jitsi.md) | `infra/jitsi/docker-compose.yml` | `meet.teamslike.com` |

---

## Architecture

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

---

## Network ports (host)

| Port | Protocol | Service | Required? |
|---|---|---|---|
| 22 | TCP | SSH | always |
| 80 | TCP | Caddy | always — HTTP → HTTPS redirect |
| 443 | TCP | Caddy | always — TLS for all three subdomains |
| **10000** | **UDP** | jvb | **only if Jitsi is deployed — without it, no video** |

Nothing else should be open. Postgres, Redis, and internal app containers do
not bind host ports.

---

## DNS

All three subdomains must resolve to this server's IP **before** first
deploy — Caddy obtains Let's Encrypt certs on first HTTPS request, and
failed cert attempts get rate-limited.

| Record | Type | Value |
|---|---|---|
| `api.teamslike.com` | A | server IP |
| `support.teamslike.com` | A | server IP |
| `meet.teamslike.com` | A | server IP |

---

## Deployment order (first time)

The API stack creates the shared `teamslike_edge` Docker network — it must
come first.

1. **API** — `docker-compose.prod.yml`. Creates the network, brings up
   Caddy + Postgres + Redis + API. See [api.md](deployment/api.md).
2. **Chatwoot** — joins `teamslike_edge`. Two-step: prepare schema, then start.
   Requires a human to create the first user in the UI and copy an access
   token into the API's `.env.prod`. See [chatwoot.md](deployment/chatwoot.md).
3. **Jitsi** — joins `teamslike_edge`. JWT secret must match the API's.
   Requires UDP 10000 open on the firewall. See [jitsi.md](deployment/jitsi.md).

Smoke test after each stack: `scripts/smoke.sh https://api.teamslike.com`.

---

## Cross-stack integration points

These are the only values that must stay in sync between two `.env` files. If
either side drifts, integrations break silently.

| API env (`infra/.env.prod`) | Other side | Matched in |
|---|---|---|
| `JITSI_JWT_APP_ID` | `JWT_APP_ID` | `infra/jitsi/.env` |
| `JITSI_JWT_APP_SECRET` | `JWT_APP_SECRET` | `infra/jitsi/.env` |
| `JITSI_PUBLIC_URL` | `PUBLIC_URL` | `infra/jitsi/.env` |
| `CHATWOOT_BASE_URL` | `FRONTEND_URL` | `infra/chatwoot/.env` |
| `CHATWOOT_USER_API_TOKEN` | *(obtained from Chatwoot UI after deploy)* | — |

Caddy reads three domain env vars in one place — `infra/.env.prod`:

| Var | Used for |
|---|---|
| `API_DOMAIN` | `api.*` block |
| `CHATWOOT_DOMAIN` | `support.*` block |
| `JITSI_DOMAIN` | `meet.*` block |

---

## Operational caveats that span stacks

1. **Bring DNS up before any stack** — Let's Encrypt rate-limits to 5 certs per domain per week. Failed cert attempts burn the quota.
2. **API → Chatwoot is a chicken-and-egg deploy**: the API needs a token that doesn't exist until a human creates the first Chatwoot admin. Plan for a brief gap; API will log Chatwoot 401s until the token is set.
3. **Jitsi JWT secret = API JWT secret** for Jitsi. They must be byte-identical. Mismatch = "authentication failed" on every join.
4. **Caddy data volume is irreplaceable.** It holds Let's Encrypt cert state. Loss → cert re-issue, which is rate-limited.
5. **Each stack's volumes are isolated by name.** Tearing down one stack with `-v` does not affect the others. Be deliberate about which `-v` you run.

---

## Smoke test

After every deploy:

```bash
scripts/smoke.sh https://api.teamslike.com
```

Probes `/health` (liveness) and `/ready` (readiness — DB+Redis reachable).
Exit 0 = all pass; non-zero = failure with body printed.

---

## Quick reference

| Need | Where |
|---|---|
| Detailed API ops | [deployment/api.md](deployment/api.md) |
| Detailed Chatwoot ops | [deployment/chatwoot.md](deployment/chatwoot.md) |
| Detailed Jitsi ops | [deployment/jitsi.md](deployment/jitsi.md) |
| Compose files | `infra/` |
| Env templates | `infra/.env.prod.example`, `infra/chatwoot/.env.example`, `infra/jitsi/.env.example` |
| Smoke test | `scripts/smoke.sh` |
| Migration files | `alembic/versions/` |
