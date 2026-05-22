# Jitsi Meet — Deployment

Self-hosted video conferencing. Four interlocked components from upstream
`jitsi/docker-jitsi-meet`. JWT auth: the TeamsLike API signs tokens, Prosody
(in this stack) verifies them. Joins the shared `teamslike_edge` network so
Caddy can proxy `meet.teamslike.com` to it.

Compose: `infra/jitsi/docker-compose.yml`
Env template: `infra/jitsi/.env.example`

---

## Stack components

| Service | Image | Role |
|---|---|---|
| `web` | `jitsi/web` | Static UI + nginx. Caddy proxies HTTPS here. |
| `prosody` | `jitsi/prosody` | XMPP server. Handles signaling + JWT auth. |
| `jicofo` | `jitsi/jicofo` | Conference focus — assigns participants to bridges. |
| `jvb` | `jitsi/jvb` | Video bridge. Relays media. **Needs UDP 10000 reachable from clients.** |

---

## Network ports

| Port | Protocol | Service | Required? |
|---|---|---|---|
| 80, 443 | TCP | Caddy → web | Already exposed by API stack's Caddy |
| **10000** | **UDP** | jvb | **MANDATORY — without it, calls connect but no video flows.** |

Open UDP/10000 on the firewall. This is the most common silent failure.

---

## Environment variables

Full template: `infra/jitsi/.env.example`. **R** = required, **O** = optional.

### Core
| Var | R/O | Notes |
|---|---|---|
| `JITSI_IMAGE_TAG` | **R** | Pin all four images to the same tag, e.g. `stable-10310`. Mixing tags causes XMPP mismatches. |
| `PUBLIC_URL` | **R** | `https://meet.teamslike.com` |
| `HTTP_PORT` | O | `8000` (container-internal). Leave default. |
| `HTTPS_PORT` | O | `8443` (container-internal). Leave default. |
| `TZ` | O | `Europe/Istanbul`. |

### Media routing
| Var | R/O | Notes |
|---|---|---|
| `DOCKER_HOST_ADDRESS` | **R** in many cases | Public IP clients see. Required when behind NAT or with multiple network interfaces. Leave empty only if Docker can auto-detect. |

### Internal component passwords
Generate each with `openssl rand -hex 32`. **These are unique to your deploy
— never reuse across environments.**

| Var | Purpose |
|---|---|
| `JICOFO_AUTH_PASSWORD` | Jicofo → Prosody XMPP auth |
| `JVB_AUTH_PASSWORD` | JVB → Prosody XMPP auth |
| `JIBRI_RECORDER_PASSWORD` | Jibri (recording) → Prosody — required even if recording is disabled |
| `JIBRI_XMPP_PASSWORD` | Same |
| `JICOFO_COMPONENT_SECRET` | Jicofo XMPP component secret |

### JWT auth (the integration with TeamsLike API)
| Var | R/O | Notes |
|---|---|---|
| `ENABLE_AUTH` | **R** | `1` — required for JWT auth. |
| `ENABLE_GUESTS` | **R** | `0` — disallow guests. Only JWT-bearing users join. |
| `AUTH_TYPE` | **R** | `jwt`. |
| `JWT_APP_ID` | **R** | **Must match `JITSI_JWT_APP_ID` in API `.env.prod`.** |
| `JWT_APP_SECRET` | **R** | **Must match `JITSI_JWT_APP_SECRET` in API `.env.prod`.** |
| `JWT_ACCEPTED_ISSUERS` | O | Comma-separated list. Default matches `JWT_APP_ID`. |
| `JWT_ACCEPTED_AUDIENCES` | O | Comma-separated list. Default matches `JWT_APP_ID`. |

### TLS
| Var | R/O | Notes |
|---|---|---|
| `ENABLE_LETSENCRYPT` | **R** | `0` — Caddy handles TLS upstream. |
| `DISABLE_HTTPS` | **R** | `1` — same reason. |

### Behavior
| Var | R/O | Notes |
|---|---|---|
| `ENABLE_RECORDING` | O | `0` — requires Jibri (separate, heavy). |
| `ENABLE_TRANSCRIPTIONS` | O | `0`. |
| `ENABLE_PREJOIN_PAGE` | O | `1` — users see device check before joining. |
| `ENABLE_WELCOME_PAGE` | O | `0` — disable the landing page. Users only enter via API-generated links. |
| `CONFIG` | **R** | Host directory holding per-component config subdirs. Created on first start. |

---

## First-time deploy

Prerequisite: API stack must be up (creates `teamslike_edge` network) and DNS
for `meet.teamslike.com` must point to this server.

```bash
cp infra/jitsi/.env.example infra/jitsi/.env
# ... edit, fill secrets ...
# CRITICAL: JWT_APP_SECRET must equal JITSI_JWT_APP_SECRET in infra/.env.prod

mkdir -p infra/jitsi/jitsi-config

docker compose --env-file infra/jitsi/.env \
  -f infra/jitsi/docker-compose.yml up -d

# Check all four containers are up
docker compose --env-file infra/jitsi/.env \
  -f infra/jitsi/docker-compose.yml ps
```

On first start each component generates its config under `${CONFIG}/web`,
`${CONFIG}/prosody`, `${CONFIG}/jicofo`, `${CONFIG}/jvb`. Back this directory
up — it contains generated XMPP secrets that pair the components.

---

## Verifying the deploy

1. **Browser test**: open `https://meet.teamslike.com/<room-name>?jwt=<token-from-API>`. Without a valid JWT you should be denied (`ENABLE_GUESTS=0`).
2. **Two-person video test from different networks** — if you can connect but see frozen video, UDP 10000 is blocked.
3. **Logs**: `docker compose -f infra/jitsi/docker-compose.yml logs -f jicofo` should show conference creation when someone joins.

---

## Subsequent upgrades

```bash
# Bump JITSI_IMAGE_TAG in infra/jitsi/.env (same tag for all 4)
docker compose --env-file infra/jitsi/.env \
  -f infra/jitsi/docker-compose.yml pull
docker compose --env-file infra/jitsi/.env \
  -f infra/jitsi/docker-compose.yml up -d
```

Jitsi releases are tagged by date (e.g. `stable-10310`). Test in staging
first — Prosody config is occasionally backward-incompatible between major
stable releases.

---

## Customization

| Want to change | Where |
|---|---|
| Branding (logo, colors) | `${CONFIG}/web/custom-config.js`, `${CONFIG}/web/interface_config.js` |
| Landing/welcome behavior | `ENABLE_WELCOME_PAGE`, `ENABLE_PREJOIN_PAGE` env vars |
| Allowed JWT issuers/audiences | `JWT_ACCEPTED_ISSUERS`, `JWT_ACCEPTED_AUDIENCES` |
| Lobby behavior | Per-room via API JWT claims (`moderator`, `lobby_bypass`) |
| Custom Prosody modules | `${CONFIG}/prosody/prosody-plugins-custom/` |

These files survive container recreation because `${CONFIG}` is a host
directory mount.

---

## Backup

| Asset | Recommendation |
|---|---|
| `${CONFIG}` host directory | Snapshot once after first start. Holds component pairing secrets. Loss = re-bootstrap entire stack. |
| Conference recordings | If `ENABLE_RECORDING=1`, snapshot whatever Jibri writes to. (Out of scope here — Jibri is a separate stack.) |
| Postgres | None — Jitsi is stateless. |

---

## Common ops

| Task | Command |
|---|---|
| Logs (all components) | `docker compose -f infra/jitsi/docker-compose.yml logs -f` |
| Logs (one component) | `docker compose -f infra/jitsi/docker-compose.yml logs -f jvb` |
| Restart Prosody (touches all auth) | `docker compose -f infra/jitsi/docker-compose.yml restart prosody jicofo jvb` |
| Verify UDP 10000 is open | From a client: `nc -u -v <server-ip> 10000` |
| Tail Jicofo conference events | `docker compose -f infra/jitsi/docker-compose.yml logs -f jicofo | grep -i conference` |

---

## Caveats

1. **UDP 10000 blocked = no video.** The most common silent failure. Verify with a real two-person call from different networks before going live.
2. **`JWT_APP_SECRET` desync** between API and Jitsi → users get "authentication failed". Both values must be identical, byte-for-byte.
3. **Image tag mixing** between web/prosody/jicofo/jvb causes XMPP schema mismatches. Use one variable (`JITSI_IMAGE_TAG`) for all four.
4. **First start writes config to `${CONFIG}`** — running with the host directory missing or read-only will silently fail. `mkdir -p infra/jitsi/jitsi-config` before first `up`.
5. **`DOCKER_HOST_ADDRESS`** matters behind NAT. If clients can connect to signaling but media fails, this is the first thing to check — set it to the public IP.
6. **No DB**, but `${CONFIG}` is irreplaceable. Snapshot it after first successful start.
