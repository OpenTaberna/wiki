---
title: Configuration
description: Environment-based configuration management
published: true
date: 2026-08-26T12:00:00.000Z
tags: configuration, settings, environment, docker, kubernetes
editor: markdown
dateCreated: 2025-12-07T09:15:00.000Z
---

# Configuration

OpenTaberna uses **environment-based configuration** that supports multiple secret sources,
so the same image runs on a laptop, in Compose and in Kubernetes without code changes.

## Configuration sources

Settings are loaded in **priority order**:

1. **Docker secrets** — `/run/secrets/{name}` (highest)
2. **Kubernetes secrets** — `/var/run/secrets/{name}`
3. **Environment variables** — `UPPERCASE_WITH_UNDERSCORES`
4. **`.env` file** — in the project root
5. **Default values** (lowest)

The point of the ordering is that a production deployment can leave `.env` describing
non-secret shape while passwords arrive from a mounted secret, and neither has to know
about the other.

## Quick start

```bash
cp .env.example .env
```

The shipped `.env.example` is already correct for the development stack. The minimum you
would change for real use:

```bash
ENVIRONMENT=development
SECRET_KEY=dev-secret-key
DATABASE_URL=postgresql+asyncpg://opentaberna:opentaberna_password@opentaberna-db:5432/opentaberna
```

> `DATABASE_URL` must use the **`postgresql+asyncpg://`** scheme. A plain `postgresql://`
> URL selects a synchronous driver and the API will fail to start.

---

## Application

| Setting | Default | Description |
|---|---|---|
| `APP_NAME` | `OpenTaberna API` | Application name |
| `APP_VERSION` | `0.1.0` | Reported in `/openapi.json` |
| `ENVIRONMENT` | `development` | `development` / `testing` / `staging` / `production` |
| `DEBUG` | `false` | Debug mode |
| `SECRET_KEY` | ⚠️ required in production | Validated on startup — see below |

`SECRET_KEY` is checked at startup: leaving it as `CHANGE_ME_IN_PRODUCTION` while
`ENVIRONMENT=production` raises and the API refuses to boot. This is deliberate. A default
signing key that silently works is worse than a service that will not start.

## Server

| Setting | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | Bind port |
| `WORKERS` | `1` | Uvicorn worker processes |
| `RELOAD` | `false` | Auto-reload on code changes |

## Database

| Setting | Default | Description |
|---|---|---|
| `DATABASE_URL` | PostgreSQL localhost | Connection string, `postgresql+asyncpg://` |
| `DATABASE_POOL_SIZE` | `20` | Connection pool size |
| `DATABASE_MAX_OVERFLOW` | `40` | Maximum pool overflow |
| `DATABASE_POOL_TIMEOUT` | `30` | Seconds to wait for a connection |
| `DATABASE_POOL_RECYCLE` | — | Recycle connections after N seconds |
| `DATABASE_POOL_PRE_PING` | — | Test connections before use |
| `DATABASE_ECHO` | `false` | Log every statement |
| `DATABASE_STATEMENT_TIMEOUT` | — | Server-side statement timeout |
| `DATABASE_COMMAND_TIMEOUT` | — | Client-side command timeout |

`DATABASE_POOL_PRE_PING` is worth turning on anywhere a connection can be closed
underneath you — a proxy with an idle timeout, a failover. It costs a round trip and saves
a class of intermittent errors that are miserable to diagnose.

## Redis

| Setting | Default | Description |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379/0` | Connection string |
| `REDIS_PASSWORD` | from secrets | Optional |

Redis is both the cache and the job queue. Losing it does not lose queued work — that is
what the [outbox](/Orders-and-Fulfillment#the-outbox) is for — but nothing runs until it is
back.

## Keycloak

| Setting | Default | Description |
|---|---|---|
| `KEYCLOAK_URL` | `http://localhost:8080` | Where the API fetches signing keys |
| `KEYCLOAK_PUBLIC_URL` | *(empty)* | Base URL in the token's `iss` claim; falls back to `KEYCLOAK_URL` |
| `KEYCLOAK_REALM` | `opentaberna` | Realm name |
| `KEYCLOAK_CLIENT_ID` | `opentaberna-api` | Expected token audience |
| `KEYCLOAK_CLIENT_SECRET` | from secrets | Confidential client secret |
| `KEYCLOAK_ADMIN_ROLE` | `admin` | Realm role required for admin endpoints |
| `KEYCLOAK_ADMIN_CLIENT_IDS` | `["opentaberna-admin-ui"]` | Clients whose tokens may reach admin endpoints |
| `KEYCLOAK_DOCS_CLIENT_ID` | `opentaberna-admin-ui` | Client the Swagger UI logs in with |
| `KEYCLOAK_JWKS_CACHE_SECONDS` | `300` | How long signing keys are cached |

Three of these carry more weight than their one-line descriptions suggest, and each has a
failure mode that looks like something else. `KEYCLOAK_PUBLIC_URL`, `KEYCLOAK_ADMIN_CLIENT_IDS`
and `KEYCLOAK_JWKS_CACHE_SECONDS` are explained in [Authorization](/Authorization) — read
that page before changing any of them.

## API behaviour

| Setting | Default | Description |
|---|---|---|
| `CORS_ORIGINS` | `["*"]` | Allowed origins — restrict in production |
| `CORS_CREDENTIALS` | `true` | Allow credentialed requests |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `LOG_FORMAT` | `console` | `console` or `json` |
| `LOG_FILE` | — | Optional log file path |
| `CACHE_ENABLED` | `true` | Enable Redis caching |
| `CACHE_TTL` | `300` | Default cache TTL, seconds |
| `RATE_LIMIT_ENABLED` | `true` | Enable rate limiting |
| `RATE_LIMIT_PER_MINUTE` | `60` | Budget per client IP |
| `FEATURE_WEBHOOKS_ENABLED` | `false` | Feature flag |

## Payments — Stripe

| Setting | Default | Description |
|---|---|---|
| `STRIPE_SECRET_KEY` | `sk_test_CHANGE_ME` | API key |
| `STRIPE_PUBLISHABLE_KEY` | `pk_test_CHANGE_ME` | Given to the storefront |
| `STRIPE_WEBHOOK_SECRET` | from secrets | Signature verification |
| `STRIPE_PAYMENT_METHODS` | `["card"]` | Accepted method types |
| `STRIPE_BANK_TRANSFER_COUNTRY` | — | ISO 3166-1 alpha-2, required for bank transfer |

In the development stack the Stripe CLI listener container generates
`STRIPE_WEBHOOK_SECRET` and mounts it at `/run/secrets/stripe_webhook_secret`, which the
API picks up through the Docker-secret source above. Set it yourself only when running
outside Compose or against a Dashboard-managed endpoint.

## Inventory

| Setting | Default | Description |
|---|---|---|
| `RESERVATION_TTL_MINUTES` | `15` | How long a checkout holds stock |

Too short and a slow payment loses its reservation mid-flow; too long and abandoned carts
hold stock nobody can buy.

## Analytics

| Setting | Default | Description |
|---|---|---|
| `SHOP_TIMEZONE` | `Europe/Berlin` | IANA timezone the shop trades in |
| `STOREFRONT_ANALYTICS_ENABLED` | `false` | Accept anonymous shopper events from the storefront |

Analytics buckets days in this zone rather than UTC, so "today" matches the operator's day.
Leave it wrong and evening orders land on the following day for any shop east of Greenwich —
the figures stay internally consistent, which is what makes it hard to notice. An unknown
zone is rejected at request time with a `422` naming the value, rather than a `500`.

`STOREFRONT_ANALYTICS_ENABLED` is off by default because cloning OpenTaberna must not
silently start collecting anything, even something that identifies nobody. While off, the
ingest endpoint returns `404`. The storefront has a matching switch in
`storefront.config.ts`; both must be on.

## Object storage — MinIO / S3

| Setting | Default | Description |
|---|---|---|
| `STORAGE_ENDPOINT_URL` | `http://localhost:9000` | S3 endpoint |
| `STORAGE_ACCESS_KEY` | `opentaberna` | Access key |
| `STORAGE_SECRET_KEY` | `opentaberna_secret` | Secret key |
| `STORAGE_BUCKET_ITEMS` | `item-images` | Product images |
| `STORAGE_BUCKET_LABELS` | `shipping-labels` | Carrier label files |
| `STORAGE_MAX_IMAGE_BYTES` | `5242880` | Largest accepted product image (5 MB) |
| `STORAGE_REGION` | `us-east-1` | Ignored by MinIO, required by the client |

`MINIO_ROOT_USER` and `MINIO_ROOT_PASSWORD` configure the MinIO container itself in the
development compose file; the API authenticates with `STORAGE_ACCESS_KEY` and
`STORAGE_SECRET_KEY`, which default to the same values.

## Carrier — DHL

| Setting | Default | Description |
|---|---|---|
| `DHL_API_BASE_URL` | sandbox URL | Parcel DE REST API base |
| `DHL_CLIENT_ID` | `CHANGE_ME` | OAuth2 client id |
| `DHL_CLIENT_SECRET` | `CHANGE_ME` | OAuth2 client secret |
| `DHL_BILLING_NUMBER` | `CHANGE_ME` | EKP billing number |
| `DHL_DEFAULT_LABEL_FORMAT` | `pdf` | `pdf` or `zpl` |

Leaving these unset is fine. Orders then ship through the manual adapter, with the admin
entering tracking numbers by hand.

## Worker and outbox

| Setting | Default | Description |
|---|---|---|
| `ARQ_MAX_JOBS` | `10` | Concurrent jobs per worker process |
| `ARQ_JOB_TIMEOUT` | `300` | Seconds before a job is killed |
| `ARQ_MAX_TRIES` | `5` | Attempts before a job is dead-lettered (`DEAD`) |
| `OUTBOX_POLL_INTERVAL` | `30` | Seconds between outbox sweeps |
| `OUTBOX_MAX_ATTEMPTS` | `5` | Enqueue attempts before an event is marked `FAILED` |

`FAILED` and `DEAD` are different failures — see
[the outbox](/Orders-and-Fulfillment#two-ways-to-fail-and-they-mean-different-things).

## Email

| Setting | Default | Description |
|---|---|---|
| `SMTP_HOST` | *(empty)* | Leave empty to skip sending entirely |
| `SMTP_PORT` | `587` | |
| `SMTP_USER` / `SMTP_PASSWORD` | *(empty)* | Authentication |
| `EMAIL_FROM` | `noreply@opentaberna.local` | Sender address |

An empty `SMTP_HOST` logs a warning instead of failing, so development does not need a
mail server.

---

## Environment-specific examples

### Development

```bash
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
LOG_FORMAT=console
RATE_LIMIT_ENABLED=false
```

### Production

```bash
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
LOG_FORMAT=json
CORS_ORIGINS=["https://yourdomain.com","https://admin.yourdomain.com"]
KEYCLOAK_PUBLIC_URL=https://auth.yourdomain.com

# Sensitive values come from mounted secrets, not from here:
#   /run/secrets/database_url
#   /run/secrets/redis_password
#   /run/secrets/keycloak_client_secret
#   /run/secrets/stripe_webhook_secret
```

## Docker secrets

```yaml
services:
  api:
    image: opentaberna/api
    secrets:
      - database_url
      - redis_password
      - keycloak_client_secret
      - stripe_webhook_secret
    environment:
      - ENVIRONMENT=production

secrets:
  database_url:
    file: ./secrets/database_url.txt
  redis_password:
    file: ./secrets/redis_password.txt
  keycloak_client_secret:
    file: ./secrets/keycloak_client_secret.txt
  stripe_webhook_secret:
    file: ./secrets/stripe_webhook_secret.txt
```

```bash
mkdir -p secrets
echo "postgresql+asyncpg://user:pass@postgres:5432/opentaberna" > secrets/database_url.txt
chmod 600 secrets/*
```

The secret **file name** is the setting name in lower case — the loader reads
`/run/secrets/database_url` for `DATABASE_URL`.

## Kubernetes secrets

```bash
kubectl create secret generic opentaberna-secrets \
  --from-literal=database_url='postgresql+asyncpg://...' \
  --from-literal=redis_password='...' \
  --from-literal=keycloak_client_secret='...'
```

```yaml
spec:
  template:
    spec:
      containers:
      - name: api
        image: opentaberna/api:latest
        env:
        - name: ENVIRONMENT
          value: "production"
        volumeMounts:
        - name: secrets
          mountPath: /var/run/secrets
          readOnly: true
      volumes:
      - name: secrets
        secret:
          secretName: opentaberna-secrets
```

## Security checklist

### Do

- Mount secrets rather than setting them as environment variables
- Generate `SECRET_KEY` with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
- Restrict `CORS_ORIGINS` to your actual domains
- Use `LOG_FORMAT=json` in production
- Keep `.env` out of version control
- Keep `KEYCLOAK_ADMIN_CLIENT_IDS` to the admin UI only

### Don't

- Commit `.env`
- Ship the default `SECRET_KEY` (the API will refuse to start, which is the point)
- Run `DEBUG=true` in production
- Leave `CORS_ORIGINS=["*"]` in production
- Add the storefront client to `KEYCLOAK_ADMIN_CLIENT_IDS`

## Troubleshooting

### The API will not start in production

Most often `SECRET_KEY` is still the placeholder. The startup validator raises on purpose.

### Configuration is not being picked up

```bash
# Is the secret actually mounted?
ls -la /run/secrets/ /var/run/secrets/

# What did the app resolve?
docker compose exec opentaberna-api \
  python -c "from app.shared.config import get_settings; print(get_settings().database_url)"
```

Remember the precedence: a mounted secret beats an environment variable, which beats
`.env`. A stale secret file silently wins over the variable you just changed.

### Database connection failures

Check the scheme is `postgresql+asyncpg://` and the host is right for where the API runs —
`opentaberna-db` inside Compose, `localhost` outside it. `/health/ready` names the failing
dependency and its error.

## See also

- [Getting Started](/Getting-Started) — initial setup
- [Authorization](/Authorization) — the Keycloak settings in context
- [Deployment](/Deployment) — production
- `/docs` on any running instance — the live API reference
