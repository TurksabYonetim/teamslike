# infra/

Compose stacks, Dockerfile, and reverse-proxy config for production deploys.

```
infra/
├── Dockerfile                    # API image (multi-stage)
├── docker-entrypoint.sh          # API container entry (migrate / serve)
├── docker-compose.dev.yml        # Local dev: postgres + redis only
├── docker-compose.prod.yml       # Prod: api + postgres + redis + caddy
├── .env.prod.example             # API env template
├── caddy/
│   └── Caddyfile                 # Routes api.* / support.* / meet.*
├── chatwoot/
│   ├── docker-compose.yml
│   └── .env.example
└── jitsi/
    ├── docker-compose.yml
    └── .env.example
```

## Full deployment docs

Read `docs/DEPLOYMENT.md` first for the overview, then the per-stack doc:

- API → `docs/deployment/api.md`
- Chatwoot → `docs/deployment/chatwoot.md`
- Jitsi → `docs/deployment/jitsi.md`
