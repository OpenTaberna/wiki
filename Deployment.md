---
title: Production Deployment
description: Guide for deploying OpenTaberna to production
published: true
date: 2026-08-26T12:00:00.000Z
tags: deployment, docker, production, setup
editor: markdown
dateCreated: 2025-12-06T15:46:53.723Z
---

# Production Deployment

## Prerequisites

- Linux server (Ubuntu 22.04+ recommended)
- Docker and Docker Compose
- Domain names with DNS configured
- At least 4GB RAM, 2 CPU cores
- 20GB+ disk

## What ships, and what does not

Read this before planning a deployment.

`docker-compose.dev.yml` starts the **whole world** — API, worker, PostgreSQL, Redis,
Keycloak, MinIO and a Stripe listener. It is a development convenience and is not suitable
for production: it binds the database and Redis to host ports, relaxes Keycloak's TLS
requirement, and stores data in bind-mounted directories next to the checkout.

`docker-compose.yml`, the production file, ships **only the API container**, attached to an
external `frontproxy_fnet` network. It assumes PostgreSQL, Redis, Keycloak, MinIO and the
worker already exist and are reachable — it does not create them.

So a production deployment is:

1. Provision the backing services yourself — managed PostgreSQL and Redis, a Keycloak
   instance, S3 or MinIO.
2. Run the worker. It is the same image as the API with a different command
   (`python -m app.worker_main app.worker.WorkerSettings`) and **it is not optional** —
   without it, no carrier label is ever created and no reservation ever expires.
3. Point the API at all of it through configuration.

## Architecture

```
Internet
   │
   ├── api.yourdomain.com    → Reverse proxy → FastAPI  :8000
   ├── auth.yourdomain.com   → Reverse proxy → Keycloak :8080
   ├── yourdomain.com        → Reverse proxy → Storefront
   └── admin.yourdomain.com  → Reverse proxy → Admin UI
                                    │
                          PostgreSQL · Redis · MinIO
                                    │
                          Worker (same image, own command)
```

## Configuration

> See the [Configuration Guide](/Configuration) for every setting, and
> [Authorization](/Authorization) for the Keycloak settings that are easy to get wrong.

Production values worth calling out:

```bash
ENVIRONMENT=production
DEBUG=false
LOG_FORMAT=json
CORS_ORIGINS=["https://yourdomain.com","https://admin.yourdomain.com"]

DATABASE_URL=postgresql+asyncpg://user:pass@postgres:5432/opentaberna
REDIS_URL=redis://redis:6379/0

KEYCLOAK_URL=http://keycloak:8080
KEYCLOAK_PUBLIC_URL=https://auth.yourdomain.com
KEYCLOAK_ADMIN_CLIENT_IDS=["opentaberna-admin-ui"]

STORAGE_ENDPOINT_URL=https://s3.yourdomain.com
```

Three of these are the ones that break deployments:

- **`KEYCLOAK_PUBLIC_URL`** must be the URL browsers use, not the internal one. It is what
  `iss` in the token will say. Get it wrong and every token is rejected as invalid issuer.
- **`SECRET_KEY`** must not be the placeholder. The API validates this at startup and
  refuses to boot — intentionally.
- **`CORS_ORIGINS`** must not stay `["*"]`.

Secrets belong in Docker or Kubernetes secrets, not in `.env`. The loader reads
`/run/secrets/{setting_name_lowercased}` before it reads the environment.

```bash
# Generate a signing key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Deploy

```bash
cd /opt
git clone https://github.com/OpenTaberna/fastapi.git opentaberna
cd opentaberna
cp .env.example .env.production   # then edit
docker compose -f docker-compose.yml --env-file .env.production up -d
```

Verify:

```bash
docker compose ps
curl http://localhost:8000/health/ready
```

`/health/ready` is the one that matters — it probes PostgreSQL and Redis and reports each.
A `200` from `/health` only means the process is alive.

## Reverse proxy

```bash
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx
```

`/etc/nginx/sites-available/opentaberna`:

```nginx
# Rate limiting zone — see the note below
limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;

server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        limit_req zone=api burst=20 nodelay;

        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    client_max_body_size 10M;   # product image uploads
}

server {
    listen 80;
    server_name auth.yourdomain.com;

    location / {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/opentaberna /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

sudo certbot --nginx -d api.yourdomain.com
sudo certbot --nginx -d auth.yourdomain.com
sudo certbot renew --dry-run
```

> **The API's own rate limiter keys on the socket address.** Behind a proxy that is the
> proxy's IP, so every request looks like one client and the limit is effectively global.
> Either rate-limit at Nginx as shown above, or change the limiter's `key_func` to read
> `X-Forwarded-For`. Running both is fine; running neither is not.

> `client_max_body_size` must be at least `STORAGE_MAX_IMAGE_BYTES` (5 MB by default) or
> image uploads fail at the proxy with a `413` the API never sees.

`proxy_set_header X-Forwarded-Proto $scheme` is not optional for Keycloak — without it,
Keycloak builds redirect URLs with `http://` and the login loop breaks.

## The worker

```bash
docker run -d --name opentaberna-worker \
  --env-file .env.production \
  --network fastapi_backend \
  opentaberna-api:latest \
  python -m app.worker_main app.worker.WorkerSettings
```

Health is a Redis ping. If the worker is down, orders reach `paid` and stop:
`outbox_events` fills with `PENDING` rows and nothing dequeues them. That is the first
place to look when nothing ships.

## Database

The API creates its schema on startup; there is no Alembic migration step today. Plan a
migration tool before the first schema change against real data.

### Backups

`/opt/opentaberna/backup.sh`:

```bash
#!/bin/bash
set -euo pipefail

BACKUP_DIR="/opt/backups/opentaberna"
DATE=$(date +%Y%m%d_%H%M%S)
POSTGRES_CONTAINER="opentaberna-db"

mkdir -p "$BACKUP_DIR"
docker exec "$POSTGRES_CONTAINER" pg_dump -U opentaberna opentaberna \
  | gzip > "$BACKUP_DIR/db_$DATE.sql.gz"

find "$BACKUP_DIR" -name "db_*.sql.gz" -mtime +30 -delete
echo "Backup completed: db_$DATE.sql.gz"
```

```bash
chmod +x /opt/opentaberna/backup.sh
# crontab: daily at 02:00
0 2 * * * /opt/opentaberna/backup.sh
```

**Back up the object store too.** Carrier labels and product images live in MinIO, not in
PostgreSQL, so a database-only backup restores orders whose labels have vanished. Use
`mc mirror` or your provider's replication.

Restore:

```bash
docker compose down
gunzip < /opt/backups/opentaberna/db_20260826_020000.sql.gz \
  | docker exec -i opentaberna-db psql -U opentaberna opentaberna
docker compose up -d
```

Test a restore before you need one. An untested backup is a hypothesis.

## Monitoring

```bash
docker compose logs -f
docker compose logs -f fastapi
docker compose logs --tail=100 fastapi
```

Set `LOG_FORMAT=json` so logs are parseable, and keep the correlation ID — it threads a
request through the API and the worker.

Log rotation in `/etc/docker/daemon.json`:

```json
{
  "log-driver": "json-file",
  "log-opts": { "max-size": "10m", "max-file": "3" }
}
```

### What to alert on

| Signal | Why |
|---|---|
| `/health/ready` non-200 | A dependency is down |
| `outbox_events` with `status='DEAD'` | A job ran and gave up — usually the carrier API |
| `outbox_events` with `status='FAILED'` | Never reached the queue — Redis or the poller |
| `outbox_events` `PENDING` and ageing | The worker is not running |
| `webhook_events` with `processed_at IS NULL` | Payments arriving but not being handled |

Those four queries are worth a dashboard. They are the difference between noticing a
stalled fulfillment pipeline in minutes and hearing about it from a customer in days.

```sql
SELECT status, count(*) FROM outbox_events GROUP BY status;
SELECT count(*) FROM webhook_events WHERE processed_at IS NULL;
```

## Updates

The `fastapi` repository has two GitHub workflows:

| Workflow | Trigger | Does |
|---|---|---|
| `test.yml` | Push / PR to main, or manual | Integration tests, pytest, ruff, Trivy, Bandit. Results uploaded as artifacts. |
| `test-build-deploy.yml` | A `vX.Y.Z` tag | Runs tests, builds the image, pushes it to the registry, deploys `docker-compose.yml` to Portainer. |

```bash
git tag v1.2.3 && git push origin v1.2.3
```

> **The deploy job reports whether Portainer accepted the stack, not whether the
> application works.** A container that starts and then fails is still "running" as far as
> that check is concerned. Always confirm `/health/ready` yourself after a deploy.

Manual update:

```bash
cd /opt/opentaberna
git pull
docker compose build
docker compose up -d --no-deps --build fastapi
curl https://api.yourdomain.com/health/ready
```

Remember to rebuild the worker too — same image, so it needs the same restart to pick up
new code.

## Security checklist

- [ ] `SECRET_KEY` generated, not the placeholder
- [ ] All default passwords changed, including Keycloak's `admin`/`admin`
- [ ] Seeded users (`adminuser`, `testuser`, `testuser2`) removed from the realm
- [ ] Direct access grants disabled on both public clients
- [ ] `KEYCLOAK_ADMIN_CLIENT_IDS` limited to the admin UI
- [ ] `CORS_ORIGINS` set to real domains
- [ ] Secrets mounted, not passed as environment variables
- [ ] TLS on every public hostname
- [ ] Database and Redis not exposed to the internet
- [ ] Rate limiting effective behind the proxy
- [ ] Firewall configured:
      `sudo ufw allow 22/tcp && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw enable`
- [ ] Backups running **and a restore tested**, database and object store
- [ ] Alerting on the queries above

## Performance

**Uvicorn workers** — `WORKERS`, rule of thumb `(2 × cores) + 1`.

**Database pool** — `DATABASE_POOL_SIZE` (20) and `DATABASE_MAX_OVERFLOW` (40) are per
process. Total connections are roughly `WORKERS × (pool_size + max_overflow)`, and that
has to stay under the server's `max_connections`. Four workers at the defaults wants up to
240 connections, which is more than a default PostgreSQL allows.

**Worker concurrency** — `ARQ_MAX_JOBS` (10 per process). Carrier APIs rate-limit; raising
this mostly buys retries.

## Troubleshooting

### Container will not start

```bash
docker compose logs fastapi
docker stats
```

A start failure with `SECRET_KEY` in the traceback is the production validator, working.

### Every token is rejected

`KEYCLOAK_PUBLIC_URL`. See [Authorization](/Authorization#issuer-urls-the-one-that-bites).

### Admin gets 403 with a valid admin token

The `azp` check. The token came from the storefront client, not the admin UI. This is the
protection working, not a bug.

### Orders are paid but nothing ships

In order: is the worker running; `SELECT status, count(*) FROM outbox_events GROUP BY
status`; then the worker logs for the correlation ID. See
[Orders and Fulfillment](/Orders-and-Fulfillment#reading-the-trail).

### Database connection issues

```bash
docker compose exec postgres psql -U opentaberna -d opentaberna -c "SELECT 1;"
docker compose exec fastapi nc -zv postgres 5432
```

## Support

- [Configuration](/Configuration) · [Authorization](/Authorization) · [Orders and Fulfillment](/Orders-and-Fulfillment)
- **API docs:** `https://api.yourdomain.com/docs`
- **Issues:** https://github.com/OpenTaberna/fastapi/issues
