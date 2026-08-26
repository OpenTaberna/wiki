---
title: Getting Started
description: Quick start guide for OpenTaberna
published: true
date: 2026-08-26T12:00:00.000Z
tags: getting-started, quickstart, setup
editor: markdown
dateCreated: 2025-12-06T15:30:00.000Z
---

# Getting Started

This guide gets the whole OpenTaberna stack running on your machine: the API and its
backing services, the back-office UI, and the storefront.

## Prerequisites

- **Docker** (20.10+) and **Docker Compose** (2.0+)
- **Git**
- **Node.js** 22.22+, 24.15+ or 26+ — only needed to run the admin UI from source
- At least 4GB of available RAM

## 1. Clone the repositories

The project is four repositories, not one. Put them side by side:

```bash
mkdir opentaberna && cd opentaberna
git clone https://github.com/OpenTaberna/fastapi.git
git clone https://github.com/OpenTaberna/frontend.git
git clone https://github.com/OpenTaberna/admin_frontend.git
git clone https://github.com/OpenTaberna/wiki.git
```

Everything below assumes you are in one of those directories.

## 2. Start the backend stack

```bash
cd fastapi
cp .env.example .env
docker compose -f docker-compose.dev.yml up -d
```

That brings up seven containers:

| Container | Purpose | Port |
|---|---|---|
| `opentaberna-api` | The FastAPI service | 8000 |
| `opentaberna-db` | PostgreSQL 17 | 5432 |
| `opentaberna-redis` | Redis 8 — cache and job queue | 6379 |
| `opentaberna-keycloak` | Keycloak 26 — identity provider | 8080 |
| `opentaberna-minio` | MinIO — product images, carrier labels | 9000 (S3), 9001 (console) |
| `opentaberna-worker` | ARQ background worker | — |
| `opentaberna-stripe-listener` | Stripe CLI, forwards test webhooks to the API | — |

Keycloak takes 30–60 seconds on a first start because it imports the realm. Watch it
settle with:

```bash
docker compose -f docker-compose.dev.yml ps
```

Every container should read `healthy` before you continue.

> **Stripe:** the listener generates its own webhook signing secret and mounts it into the
> API, so you never copy a `whsec_...` by hand. You only need a test-mode
> `STRIPE_SECRET_KEY` in `.env` if you intend to exercise payment.

## 3. Verify the API

```bash
curl http://localhost:8000/health
```

```json
{
  "status": "ok",
  "timestamp": "2026-08-26T11:54:20.342282Z"
}
```

`/health` is a liveness probe and answers as soon as the process is up. To check that the
API can actually reach its dependencies, use the readiness probe:

```bash
curl http://localhost:8000/health/ready
```

```json
{
  "status": "ok",
  "timestamp": "2026-08-26T11:54:20.446532Z",
  "database": { "healthy": true, "latency_ms": 3.13, "error": null },
  "redis":    { "healthy": true, "latency_ms": 2.34, "error": null }
}
```

> Note that `GET /` is **not** an endpoint — it returns 404. There is no root version
> route; use `/health` or read `info.version` from `/openapi.json`.

## 4. Start the frontends

**Storefront** — runs as a container that serves the built app and proxies `/api` to the
API on your host:

```bash
cd ../frontend
docker compose up --build -d     # http://localhost:4300
```

**Admin UI** — run from source:

```bash
cd ../admin_frontend
npm install
npm start                        # http://localhost:4200
```

## 5. Sign in

The realm ships three development users. Passwords are in the realm import and are
development-only.

| Username | Password | Role | Use it for |
|---|---|---|---|
| `adminuser` | `adminpassword` | `admin` | The admin UI, and every `/v1/admin/**` endpoint |
| `testuser` | `testpassword` | `customer` | The storefront |
| `testuser2` | `testpassword2` | `customer` | Testing that one customer cannot read another's data |

The Keycloak admin console is at **http://localhost:8080** (`admin` / `admin`).

## Where everything lives

| Service | URL |
|---|---|
| **API documentation (Swagger)** | http://localhost:8000/docs |
| **OpenAPI schema** | http://localhost:8000/openapi.json |
| **Storefront** | http://localhost:4300 |
| **Admin UI** | http://localhost:4200 |
| **Keycloak** | http://localhost:8080 |
| **MinIO console** | http://localhost:9001 |

## Your first API call

The catalogue is public — browsing needs no token:

```bash
curl http://localhost:8000/v1/items/
```

Note the prefix is `/v1`, **not** `/api/v1`. (The storefront container proxies `/api/v1`
to `/v1`, which is why you may see that path in browser dev tools.)

Everything else needs a bearer token. In development you can take a shortcut through
Keycloak's direct grant:

```bash
TOKEN=$(curl -s -X POST \
  http://localhost:8080/realms/opentaberna/protocol/openid-connect/token \
  -d "client_id=opentaberna-admin-ui" \
  -d "grant_type=password" \
  -d "username=adminuser" \
  -d "password=adminpassword" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/v1/admin/orders/
```

The same call without the header returns `403`. Which client the token came from matters
as much as the role on it — see [Authorization](/Authorization).

You can also log in inside the Swagger UI: `/docs` is wired to the Keycloak realm, so the
padlocked operations can be tried out rather than only read.

## Running the API outside Docker

For work on the API itself, run the service on your host and leave the backing containers
running:

```bash
cd fastapi
uv sync
source .venv/bin/activate
python3 src/app/main.py
```

The project uses **uv**, not pip, and targets Python 3.14.

## Development workflow

```bash
# All logs
docker compose -f docker-compose.dev.yml logs -f

# One service
docker compose -f docker-compose.dev.yml logs -f opentaberna-api

# Stop
docker compose -f docker-compose.dev.yml down

# Stop and wipe the database, object store and Keycloak users
docker compose -f docker-compose.dev.yml down -v
```

> `down -v` also removes the `keycloak_data` volume, so registered users and their role
> grants are gone. The three seeded users come back on the next start; anyone you created
> by hand does not.

## Common issues

### A port is already in use

The stack claims 8000, 5432, 6379, 8080, 9000 and 9001, and the frontends claim 4200 and
4300. Find the offender with `lsof -nP -iTCP:8000 -sTCP:LISTEN`, then either stop it or
remap the port in `docker-compose.dev.yml`.

The admin UI takes `--port`:

```bash
npm start -- --port 4201
```

Keycloak only permits redirects back to the ports in the realm import
(4200, 4300, 8081, 8082), so a frontend moved to an unlisted port will fail login until
you add it to the client's redirect URIs.

### Keycloak is unhealthy or the admin console refuses HTTP

The dev compose file relaxes `sslRequired` on the master realm on every start, because
Docker's port forwarding makes a request from your host look non-local and Keycloak would
otherwise refuse plain HTTP. If the console is unreachable, check that the container
finished booting:

```bash
docker compose -f docker-compose.dev.yml logs opentaberna-keycloak | tail -20
```

### The API starts but readiness fails

`/health/ready` names the dependency that is down and the error it returned. A `database`
failure with the API otherwise healthy usually means `DATABASE_URL` in `.env` still points
at `localhost` while the API is running inside Compose, where the host is
`opentaberna-db`.

## Next steps

- [API Architecture](/API/Architecture) — every endpoint, the response envelope, errors
- [Authorization](/Authorization) — roles, clients, and what the API enforces
- [Orders and Fulfillment](/Orders-and-Fulfillment) — the order lifecycle end to end
- [Database Architecture](/Database/Architecture) — the real schema
- [Configuration](/Configuration) — every setting and where it can come from
- [Deployment](/Deployment) — running this in production

For developer-facing detail the wiki does not carry, the `fastapi` repository has
`docs/architecture.md`, `docs/development.md`, `docs/testing.md` and
`docs/authorization.md`.
