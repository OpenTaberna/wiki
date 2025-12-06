---
title: Production Deployment
description: Guide for deploying OpenTaberna to production
published: true
date: 2025-12-06T15:30:00.000Z
tags: deployment, production, docker, setup
editor: markdown
dateCreated: 2025-12-06T15:30:00.000Z
---

# Production Deployment

This guide covers deploying OpenTaberna to a production environment.

## Prerequisites

- Linux server (Ubuntu 22.04+ recommended)
- Docker & Docker Compose installed
- Domain name with DNS configured
- At least 4GB RAM, 2 CPU cores
- 20GB+ disk space

## Architecture Overview

```
Internet → Reverse Proxy (Nginx) → FastAPI
                                  → Keycloak
                                  → Admin UI
                                  → Frontend
         ↓
    PostgreSQL, Redis
```

## Environment Configuration

### 1. Create Production Environment File

Create `.env.production`:

```bash
# Application
APP_ENV=production
APP_NAME=OpenTaberna
APP_VERSION=0.1.0
SECRET_KEY=<generate-strong-secret-key>

# Database
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=opentaberna
POSTGRES_USER=opentaberna
POSTGRES_PASSWORD=<strong-password>

# Redis
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=<strong-password>

# Keycloak
KEYCLOAK_URL=https://auth.yourdomain.com
KEYCLOAK_REALM=opentaberna
KEYCLOAK_CLIENT_ID=opentaberna-api
KEYCLOAK_CLIENT_SECRET=<from-keycloak-admin>

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json

# CORS (adjust to your frontend domains)
CORS_ORIGINS=https://yourdomain.com,https://admin.yourdomain.com
```

### 2. Generate Secrets

```bash
# Generate SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Generate database password
openssl rand -base64 32

# Generate Redis password
openssl rand -base64 32
```

## Deployment Steps

### 1. Clone Repository

```bash
cd /opt
git clone https://github.com/PhilippTheServer/opentaberna.git
cd opentaberna
```

### 2. Configure Environment

```bash
cp .env.example .env.production
nano .env.production  # Edit with your values
```

### 3. Start Services

```bash
docker-compose -f docker-compose.yml --env-file .env.production up -d
```

### 4. Verify Services

```bash
# Check all containers are running
docker-compose ps

# Check API health
curl http://localhost:8000/health

# View logs
docker-compose logs -f fastapi
```

## Reverse Proxy Setup (Nginx)

### Install Nginx

```bash
sudo apt update
sudo apt install nginx certbot python3-certbot-nginx
```

### Configure Nginx

Create `/etc/nginx/sites-available/opentaberna`:

```nginx
# API Backend
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # API Documentation
    location /docs {
        proxy_pass http://localhost:8000/docs;
        proxy_set_header Host $host;
    }

    location /openapi.json {
        proxy_pass http://localhost:8000/openapi.json;
        proxy_set_header Host $host;
    }

    client_max_body_size 100M;
}

# Keycloak
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

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/opentaberna /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Setup SSL with Let's Encrypt

```bash
# API
sudo certbot --nginx -d api.yourdomain.com

# Keycloak
sudo certbot --nginx -d auth.yourdomain.com

# Auto-renewal
sudo certbot renew --dry-run
```

## Database Setup

### Initial Migration

```bash
# Run migrations
docker-compose exec fastapi alembic upgrade head

# Create initial admin user (if applicable)
docker-compose exec fastapi python -m app.scripts.create_admin
```

### Backup Strategy

#### Automated Daily Backups

Create `/opt/opentaberna/backup.sh`:

```bash
#!/bin/bash

BACKUP_DIR="/opt/backups/opentaberna"
DATE=$(date +%Y%m%d_%H%M%S)
POSTGRES_CONTAINER="opentaberna-postgres-1"

mkdir -p $BACKUP_DIR

# Backup database
docker exec $POSTGRES_CONTAINER pg_dump -U opentaberna opentaberna | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Keep only last 30 days
find $BACKUP_DIR -name "db_*.sql.gz" -mtime +30 -delete

echo "Backup completed: db_$DATE.sql.gz"
```

Make executable and add to cron:

```bash
chmod +x /opt/opentaberna/backup.sh

# Add to crontab (runs daily at 2 AM)
sudo crontab -e
0 2 * * * /opt/opentaberna/backup.sh
```

#### Restore from Backup

```bash
# Stop services
docker-compose down

# Restore database
gunzip < /opt/backups/opentaberna/db_20251206_020000.sql.gz | \
  docker exec -i opentaberna-postgres-1 psql -U opentaberna opentaberna

# Restart services
docker-compose up -d
```

## Monitoring & Logging

### View Logs

```bash
# Real-time logs
docker-compose logs -f

# Specific service
docker-compose logs -f fastapi

# Last 100 lines
docker-compose logs --tail=100 fastapi
```

### Log Rotation

Docker handles log rotation, but configure limits in `/etc/docker/daemon.json`:

```json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

Restart Docker:

```bash
sudo systemctl restart docker
```

### Health Checks

Create `/opt/opentaberna/healthcheck.sh`:

```bash
#!/bin/bash

API_URL="https://api.yourdomain.com/health"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $API_URL)

if [ $RESPONSE -eq 200 ]; then
    echo "API is healthy"
    exit 0
else
    echo "API is down! Status: $RESPONSE"
    # Send alert (email, Slack, etc.)
    exit 1
fi
```

Add to cron (every 5 minutes):

```bash
*/5 * * * * /opt/opentaberna/healthcheck.sh
```

## Updates & Maintenance

### Update to Latest Version

```bash
cd /opt/opentaberna

# Pull latest code
git pull

# Rebuild containers
docker-compose build

# Run migrations
docker-compose run fastapi alembic upgrade head

# Restart services (zero-downtime)
docker-compose up -d --no-deps --build fastapi
```

### Zero-Downtime Deployment

For production with multiple instances:

```bash
# Scale to 2 instances
docker-compose up -d --scale fastapi=2

# Update one instance
docker-compose up -d --no-deps --scale fastapi=2 fastapi

# Scale back to 1 if needed
docker-compose up -d --scale fastapi=1
```

## Security Checklist

- [ ] Change all default passwords
- [ ] Use strong SECRET_KEY
- [ ] Configure firewall (UFW):
  ```bash
  sudo ufw allow 22/tcp    # SSH
  sudo ufw allow 80/tcp    # HTTP
  sudo ufw allow 443/tcp   # HTTPS
  sudo ufw enable
  ```
- [ ] Enable SSL/TLS (Let's Encrypt)
- [ ] Restrict database to localhost only
- [ ] Set CORS_ORIGINS to specific domains
- [ ] Enable rate limiting in Nginx:
  ```nginx
  limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
  limit_req zone=api burst=20 nodelay;
  ```
- [ ] Regular backups enabled
- [ ] Monitoring/alerting configured
- [ ] Keep Docker images updated

## Performance Tuning

### Database Connection Pool

In your application config:

```python
# src/app/shared/database.py
SQLALCHEMY_POOL_SIZE = 20
SQLALCHEMY_MAX_OVERFLOW = 40
SQLALCHEMY_POOL_TIMEOUT = 30
```

### Uvicorn Workers

In `docker-compose.yml`:

```yaml
command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Rule of thumb: `workers = (2 * CPU_cores) + 1`

### Redis Caching

Enable caching for frequently accessed data:

```python
# Cache item queries for 5 minutes
@cache(expire=300)
async def get_item(item_id: str):
    return await db.get_item(item_id)
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs fastapi

# Check resource usage
docker stats

# Restart specific service
docker-compose restart fastapi
```

### Database Connection Issues

```bash
# Check database is running
docker-compose exec postgres psql -U opentaberna -d opentaberna -c "SELECT 1;"

# Check connection from FastAPI container
docker-compose exec fastapi nc -zv postgres 5432
```

### High Memory Usage

```bash
# Check memory usage
docker stats

# Restart services
docker-compose restart

# Clear Redis cache
docker-compose exec redis redis-cli FLUSHALL
```

### SSL Certificate Issues

```bash
# Test certificate renewal
sudo certbot renew --dry-run

# Force renewal
sudo certbot renew --force-renewal

# Check certificate expiry
sudo certbot certificates
```

## API Documentation

Remember: The complete API documentation is always available at:

**https://api.yourdomain.com/docs**

This is automatically generated by FastAPI and is always up-to-date with your deployment.

## Support

- **GitHub Issues:** https://github.com/PhilippTheServer/opentaberna/issues
- **API Docs:** https://api.yourdomain.com/docs
- **Wiki:** https://wiki.opentaberna.dev
