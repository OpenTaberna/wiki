---
title: Configuration
description: Environment-based configuration management
published: true
date: 2025-12-07T09:15:00.000Z
tags: configuration, settings, environment, docker, kubernetes
editor: markdown
dateCreated: 2025-12-07T09:15:00.000Z
---

# Configuration

OpenTaberna uses **environment-based configuration** that supports multiple secret sources for maximum flexibility in different deployment scenarios.

## Configuration Sources

Settings are loaded in **priority order**:

1. **Docker Secrets** (highest priority)
   - `/run/secrets/{secret_name}`
   
2. **Kubernetes Secrets**
   - `/var/run/secrets/{secret_name}`
   
3. **Environment Variables**
   - `UPPERCASE_WITH_UNDERSCORES`
   
4. **.env File**
   - `.env` in project root
   
5. **Default Values** (lowest priority)

## Quick Start

### Development Setup

1. **Copy the example file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit settings:**
   ```bash
   nano .env
   ```

3. **Minimal configuration:**
   ```bash
   ENVIRONMENT=development
   SECRET_KEY=dev-secret-key
   DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/opentaberna
   ```

### Production Setup

For production, use **Docker or Kubernetes secrets** for sensitive values:

```bash
# Don't put passwords in .env!
# Use secrets instead:
echo "postgresql://prod-db/db" > /run/secrets/database_url
echo "redis-password" > /run/secrets/redis_password
```

## Key Settings

### Application

| Setting | Default | Description |
|---------|---------|-------------|
| `APP_NAME` | `OpenTaberna API` | Application name |
| `ENVIRONMENT` | `development` | Environment: development/testing/staging/production |
| `SECRET_KEY` | ⚠️ Required in production | Secret key for JWT/sessions |
| `DEBUG` | Auto (true in dev) | Debug mode |

### Database

| Setting | Default | Description |
|---------|---------|-------------|
| `DATABASE_URL` | PostgreSQL localhost | Database connection string |
| `DATABASE_POOL_SIZE` | `20` | Connection pool size |
| `DATABASE_MAX_OVERFLOW` | `40` | Maximum pool overflow |

### Redis

| Setting | Default | Description |
|---------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `REDIS_PASSWORD` | From secrets | Redis password (optional) |

### Keycloak

| Setting | Default | Description |
|---------|---------|-------------|
| `KEYCLOAK_URL` | `http://localhost:8080` | Keycloak server URL |
| `KEYCLOAK_REALM` | `opentaberna` | Keycloak realm name |
| `KEYCLOAK_CLIENT_ID` | `opentaberna-api` | OAuth2 client ID |
| `KEYCLOAK_CLIENT_SECRET` | From secrets | OAuth2 client secret |

### API Behavior

| Setting | Default | Description |
|---------|---------|-------------|
| `CORS_ORIGINS` | `["*"]` | Allowed CORS origins (restrict in production!) |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `LOG_FORMAT` | `console` | Log format: console or json |
| `CACHE_ENABLED` | `true` | Enable Redis caching |
| `RATE_LIMIT_ENABLED` | `true` | Enable rate limiting |

## Environment-Specific Configuration

### Development

```bash
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=DEBUG
LOG_FORMAT=console
DATABASE_URL=postgresql+asyncpg://dev:dev@localhost/opentaberna_dev
```

### Production

```bash
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=INFO
LOG_FORMAT=json
CORS_ORIGINS=["https://yourdomain.com"]

# Sensitive values from secrets:
# - DATABASE_URL from /run/secrets/database_url
# - REDIS_PASSWORD from /run/secrets/redis_password
# - KEYCLOAK_CLIENT_SECRET from /run/secrets/keycloak_client_secret
```

## Docker Secrets

### docker-compose.yml

```yaml
services:
  api:
    image: opentaberna/api
    secrets:
      - database_url
      - redis_password
      - keycloak_client_secret
    environment:
      - ENVIRONMENT=production

secrets:
  database_url:
    file: ./secrets/database_url.txt
  redis_password:
    file: ./secrets/redis_password.txt
  keycloak_client_secret:
    file: ./secrets/keycloak_client_secret.txt
```

### Create Secret Files

```bash
mkdir -p secrets
echo "postgresql://user:pass@postgres:5432/opentaberna" > secrets/database_url.txt
echo "redis-secure-password" > secrets/redis_password.txt
echo "keycloak-client-secret" > secrets/keycloak_client_secret.txt
chmod 600 secrets/*
```

## Kubernetes Secrets

### Create Secret

```bash
kubectl create secret generic opentaberna-secrets \
  --from-literal=database_url='postgresql://...' \
  --from-literal=redis_password='secret123' \
  --from-literal=keycloak_client_secret='oauth-secret'
```

### Mount in Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: opentaberna-api
spec:
  template:
    spec:
      containers:
      - name: api
        image: opentaberna/api:latest
        env:
        - name: ENVIRONMENT
          value: "production"
        - name: SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: opentaberna-secrets
              key: secret_key
        volumeMounts:
        - name: secrets
          mountPath: /var/run/secrets
          readOnly: true
      volumes:
      - name: secrets
        secret:
          secretName: opentaberna-secrets
```

## Security Best Practices

### ✅ Do

- Use Docker/K8s secrets for sensitive data in production
- Change `SECRET_KEY` to a strong random value
- Restrict `CORS_ORIGINS` to specific domains
- Use `LOG_FORMAT=json` in production for structured logging
- Keep `.env` files out of version control (`.gitignore`)

### ❌ Don't

- Commit `.env` files to git
- Use default `SECRET_KEY` in production
- Use `DEBUG=true` in production
- Allow `CORS_ORIGINS=["*"]` in production
- Store passwords in environment variables (use secrets!)

## Validation

The configuration system validates settings on startup:

```python
# SECRET_KEY must be changed in production
if environment == "production" and secret_key == "CHANGE_ME_IN_PRODUCTION":
    raise ValueError("SECRET_KEY must be changed in production!")
```

## Troubleshooting

### Configuration Not Loading

```bash
# Check environment variables
env | grep OPENTABERNA

# Check if secrets exist
ls -la /run/secrets/
ls -la /var/run/secrets/
```

### Database Connection Issues

```bash
# Verify DATABASE_URL format
# postgresql+asyncpg://user:password@host:port/database

# Test connection
docker-compose exec api python -c "from app.shared.config import get_settings; print(get_settings().database_url)"
```

### Secret Key Validation Error

```bash
# Generate a secure secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Set it in production
export SECRET_KEY="<generated-key>"
```

## See Also

- [Getting Started](/Getting-Started) - Initial setup guide
- [Deployment](/Deployment) - Production deployment
- [API Documentation](http://localhost:8000/docs) - Live API reference
