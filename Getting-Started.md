---
title: Getting Started
description: Quick start guide for OpenTaberna
published: true
date: 2025-12-06T15:30:00.000Z
tags: getting-started, quickstart, setup
editor: markdown
dateCreated: 2025-12-06T15:30:00.000Z
---

# Getting Started

This guide will help you get OpenTaberna up and running in minutes.

## Prerequisites

Before you begin, ensure you have the following installed:

- **Docker** (20.10+) and **Docker Compose** (2.0+)
- **Git**
- At least 4GB of available RAM

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/PhilippTheServer/opentaberna.git
cd opentaberna
```

### 2. Start the Development Environment

```bash
docker-compose -f docker-compose.dev.yml up -d
```

This will start:
- PostgreSQL Database
- FastAPI Backend (with auto-reload)
- Keycloak (User Management)
- Redis (Cache & Queue)

### 3. Access the Services

Once all containers are running:

| Service | URL | Credentials |
|---------|-----|-------------|
| **API Documentation** | http://localhost:8000/docs | - |
| **API (OpenAPI JSON)** | http://localhost:8000/openapi.json | - |
| **Keycloak Admin** | http://localhost:8080 | admin / admin |
| **Database** | localhost:5432 | See docker-compose |

### 4. Verify Installation

Check if the API is running:

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "0.1.0"
}
```

### 5. Explore the API

Open your browser and navigate to:

**http://localhost:8000/docs**

This is FastAPI's interactive API documentation (Swagger UI). Here you can:
- Browse all available endpoints
- Test API calls directly in the browser
- See request/response schemas
- Generate code examples

## First API Call

### Without Authentication

```bash
# Get API version
curl http://localhost:8000/
```

### With Authentication

1. **Get Access Token from Keycloak:**

```bash
curl -X POST http://localhost:8080/realms/opentaberna/protocol/openid-connect/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=opentaberna-client" \
  -d "grant_type=password" \
  -d "username=admin" \
  -d "password=admin"
```

2. **Use the token:**

```bash
TOKEN="<your_access_token>"

curl http://localhost:8000/api/v1/items \
  -H "Authorization: Bearer $TOKEN"
```

## Development Workflow

### View Logs

```bash
# All services
docker-compose -f docker-compose.dev.yml logs -f

# Specific service
docker-compose -f docker-compose.dev.yml logs -f fastapi
```

### Stop Services

```bash
docker-compose -f docker-compose.dev.yml down
```

### Reset Database

```bash
docker-compose -f docker-compose.dev.yml down -v
docker-compose -f docker-compose.dev.yml up -d
```

## Project Structure

```
opentaberna/
├── fastapi_opentaberna/     # Backend API
│   ├── src/app/
│   │   ├── main.py          # FastAPI application
│   │   ├── shared/          # Shared utilities (logger, etc.)
│   │   ├── authorize/       # Keycloak integration
│   │   └── services/        # Feature modules
│   ├── tests/               # Test suite
│   └── docs/                # Developer documentation
├── wiki/                    # End-user documentation
└── docker-compose.yml       # Production setup
```

## Next Steps

### For End Users:
- Read [Configuration Guide](/Configuration) for detailed settings
- Read [Deployment Guide](/Deployment) for production setup
- Check `/docs` on your API instance for endpoint documentation

### For Developers:
- See `fastapi_opentaberna/docs/architecture.md` for architecture overview
- See `fastapi_opentaberna/docs/development.md` for development workflows
- See `fastapi_opentaberna/docs/testing.md` for testing guidelines
- See `fastapi_opentaberna/docs/config.md` for configuration module details

## Common Issues

### Port Already in Use

If port 8000 or 5432 is already in use:

1. Edit `docker-compose.dev.yml`
2. Change the port mapping:
   ```yaml
   ports:
     - "8001:8000"  # Change 8000 to 8001
   ```

### Database Connection Issues

```bash
# Check if PostgreSQL is running
docker-compose -f docker-compose.dev.yml ps

# View database logs
docker-compose -f docker-compose.dev.yml logs postgres
```

### Keycloak Not Starting

Keycloak needs time to initialize (30-60 seconds). Check logs:

```bash
docker-compose -f docker-compose.dev.yml logs keycloak
```

## Getting Help

- **API Documentation:** http://localhost:8000/docs (always up-to-date!)
- **GitHub Issues:** https://github.com/PhilippTheServer/opentaberna/issues
- **Wiki:** https://wiki.opentaberna.dev

## Summary

You now have OpenTaberna running locally! The most important resource is:

**👉 http://localhost:8000/docs**

This page contains the complete, always up-to-date API documentation with:
- All endpoints
- Request/response schemas
- Interactive testing
- Authentication examples

Everything you need to integrate with OpenTaberna is documented there automatically by FastAPI.
