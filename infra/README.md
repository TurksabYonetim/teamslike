# TeamsLike — Infrastructure

Three independent compose stacks share a single Caddy reverse proxy and a single
public IP for TLS termination:

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

Each stack has its **own** Postgres and Redis — never cross them.

---

## Deployment order

DNS must already point all three subdomains to this server's IP.

### 1. API (must come first — creates the shared `teamslike_edge` network)

```bash
cp infra/.env.prod.example infra/.env.prod      # fill secrets
docker compose --env-file infra/.env.prod -f infra/docker-compose.prod.yml up -d --build
```

This creates the `teamslike_edge` network. Verify with `docker network ls`.

### 2. Chatwoot

```bash
cp infra/chatwoot/.env.example infra/chatwoot/.env   # fill secrets
# First-time DB prepare
docker compose --env-file infra/chatwoot/.env -f infra/chatwoot/docker-compose.yml \
  run --rm rails bundle exec rails db:chatwoot_prepare
docker compose --env-file infra/chatwoot/.env -f infra/chatwoot/docker-compose.yml up -d
```

After Chatwoot starts: create an admin user via the web UI, then in Profile →
Access Token, copy the token into `infra/.env.prod` as `CHATWOOT_USER_API_TOKEN`,
then restart the API: `docker compose -f infra/docker-compose.prod.yml restart api`.

### 3. Jitsi

```bash
cp infra/jitsi/.env.example infra/jitsi/.env    # fill secrets
# JWT_APP_SECRET MUST equal JITSI_JWT_APP_SECRET in infra/.env.prod
docker compose --env-file infra/jitsi/.env -f infra/jitsi/docker-compose.yml up -d
```

Open UDP/10000 on the firewall — without it video will not flow.

---

## Operational notes

| Concern | Where |
|---|---|
| Postgres backups | `docker exec teamslike-postgres-1 pg_dump ...` — schedule via cron |
| Restart a single service | `docker compose -f infra/<stack>/docker-compose.yml restart <svc>` |
| View logs | `docker compose ... logs -f --tail=200 <svc>` |
| TLS cert renewal | Automatic via Caddy. Certs persist in `caddy_data` volume — never delete |
| Update an image | Bump tag in respective env file → `docker compose pull && up -d` |
| Pin images by digest | Replace tag with `image@sha256:...` after `docker pull` |

## Tearing down (DANGEROUS — wipes data)

```bash
# Per stack — `-v` removes volumes
docker compose -f infra/jitsi/docker-compose.yml down -v
docker compose -f infra/chatwoot/docker-compose.yml down -v
docker compose -f infra/docker-compose.prod.yml down -v
```
