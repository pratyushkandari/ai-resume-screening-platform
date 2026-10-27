# Deployment guide

Production runs on **AWS EC2 with Docker Compose**: one virtual machine runs the
four containers defined in [`docker-compose.yml`](../docker-compose.yml).
Kubernetes (`k8s/`) and Render (`render.yaml`) templates are alternatives and are
not what production uses.

```
Internet ──► EC2 security group (80/443, 22 from your IP only)
              │
              ▼
        ┌─────────────── EC2 instance (Docker Engine + Compose) ───────────────┐
        │  frontend  Nginx :80   serves the React build, proxies /api, /docs   │
        │      │                                                               │
        │      ▼                                                               │
        │  backend   FastAPI :8000 (bound to 127.0.0.1) ── uploads volume      │
        │      │                 │                                             │
        │      ▼                 ▼                                             │
        │  db  PostgreSQL :5432  redis :6379   (both bound to 127.0.0.1)       │
        │      └── pgdata volume (on the instance's EBS disk)                  │
        └──────────────────────────────────────────────────────────────────────┘
```

Only Nginx is reachable from outside. The API, database and Redis ports are bound
to `127.0.0.1` on the host, so they are not exposed even if a security-group rule
is too broad.

## 1. Instance

| Item | Recommendation | Why |
|---|---|---|
| OS | Ubuntu 22.04/24.04 LTS (x86_64) | The images are built for amd64 |
| Size | 4 GB RAM or more (e.g. `t3.medium`); 2 GB is tight | The API loads PyTorch and the embedding model in memory, next to PostgreSQL, Redis and Nginx |
| Disk | 20 GB+ gp3 EBS | Docker images (CPU PyTorch, model), database and uploaded files |
| Security group | inbound 80 (and 443 with HTTPS) from anywhere; 22 from **your IP only**; nothing else | Never open 5432, 6379 or 8000 |
| IAM / keys | SSH key pair or AWS Systems Manager Session Manager | No credentials are stored in the repository |

These sizes are estimates for this stack, not measurements; watch `docker stats`
after the first deployment and resize if memory is close to the limit.

## 2. First deployment

```bash
# On the instance
sudo apt-get update && sudo apt-get install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sudo sh          # Docker Engine + Compose plugin
sudo usermod -aG docker "$USER" && newgrp docker

git clone https://github.com/pratyushkandari/ai-resume-screening-platform.git
cd ai-resume-screening-platform
cp .env.example .env
nano .env
#   POSTGRES_PASSWORD=<long random value>
#   JWT_SECRET_KEY=<python3 -c "import secrets; print(secrets.token_urlsafe(48))">
#   HR_SIGNUP_CODE=<code you give to recruiters>   (empty = recruiter sign-up disabled)
#   CORS_ORIGINS=http://<your-domain-or-public-ip>
#   Leave APP_ENV and REQUIRE_EMBEDDING_MODEL commented out: Compose then runs in production mode.
chmod 600 .env

docker compose up -d --build        # first build downloads PyTorch and the model
docker compose ps                   # all services "running"/"healthy"
curl -s localhost/healthz           # {"status":"ok",...}
curl -s localhost/readyz            # "ready" once the database and model are up
```

Open `http://<public-ip>/` in a browser. Create the first recruiter either with the
access code on the sign-up screen or with:

```bash
docker compose exec backend python manage.py create-user --name "Jane Recruiter" --email jane@acme.com --role hr
```

## 3. HTTPS

The repository's Nginx config listens on port 80 only. Serve the site over HTTPS
before real users log in (tokens and resumes travel in every request). Two common
options:

* **Application Load Balancer + AWS Certificate Manager** (managed certificate):
  ALB listener 443 → target group → instance port 80; redirect 80 → 443. Nginx
  then sees the ALB's address as the client, so tell it to trust the ALB's
  `X-Forwarded-For` (otherwise all users share one login rate-limit counter). In
  the `server` block of `frontend/nginx.conf`, with your VPC range:
  ```nginx
  set_real_ip_from 172.31.0.0/16;   # your VPC CIDR (the ALB's addresses)
  real_ip_header   X-Forwarded-For;
  real_ip_recursive on;
  ```
  Nginx keeps overwriting the header it sends to the API with the resolved client
  address, so clients still cannot spoof their IP.
* **Certbot on the instance**: terminate TLS in the frontend Nginx (add a 443
  server block and mount the certificates) or in a small reverse proxy in front.

Then set `CORS_ORIGINS=https://<your-domain>` in `.env` and run `docker compose up -d`.

## 4. Updating to a new version

```bash
cd ai-resume-screening-platform
git pull
docker compose up -d --build        # rebuilds changed images, recreates containers
docker image prune -f               # optional: remove old image layers
```

Data in the `pgdata` and `uploads` volumes is kept across rebuilds.

## 5. Upgrading an instance that runs version 2.x (commit `c97e84d` or earlier)

Version 3 changed the Compose file. Do these steps once, in this order:

1. **Back up first** (see section 6).
2. **Rotate the published secrets.** The old Compose file contained the database
   password and the JWT secret in plain text, and they remain visible in the
   public Git history. Choose new values:
   ```bash
   docker compose exec db psql -U resume_user1 -d resume_db1 \
     -c "ALTER USER resume_user1 PASSWORD '<new password>';"
   ```
   Put the same new password in `.env` as `POSTGRES_PASSWORD`, and a new
   `JWT_SECRET_KEY` (everyone signs in again, which is expected).
3. **Close old ports.** Version 2 published 5432, 6379 and 8000 on all interfaces.
   Make sure the security group only allows 80/443 (and 22 from your IP).
4. **Keep the uploaded resumes.** Version 2 stored them in `./backend/uploads` on
   the host; version 3 uses the `uploads` Docker volume and runs as user 10001:
   ```bash
   git pull && docker compose up -d --build
   docker compose cp backend/uploads/. backend:/app/uploads/
   docker compose exec -u root backend chown -R 10001:10001 /app/uploads
   ```
5. **Passwords stored in plaintext** by very old versions no longer work; reset
   them with `docker compose exec backend python manage.py reset-password --email ...`.

The database schema needs no migration: version 3 reads the existing tables and
merges case-duplicate skills at start-up.

## 6. Backups and restore

```bash
# Database (custom format, compressed)
docker compose exec -T db pg_dump -U resume_user1 -Fc resume_db1 > backup_$(date +%F).dump
# Uploaded files
docker compose cp backend:/app/uploads ./uploads_backup_$(date +%F)

# Restore
docker compose exec -T db pg_restore -U resume_user1 -d resume_db1 --clean < backup_YYYY-MM-DD.dump
```

Copy backups off the instance (for example to S3), or enable scheduled EBS
snapshots for the volume that holds `/var/lib/docker`.

## 7. Operating it

| Task | Command |
|---|---|
| Logs | `docker compose logs -f backend` (each line has a request ID) |
| Health | `curl -s localhost/healthz`, `curl -s localhost/readyz` |
| Metrics | `curl -s localhost:8000/metrics` on the instance (not proxied publicly) |
| Restart one service | `docker compose restart backend` |
| Resource usage | `docker stats` |

Containers use `restart: unless-stopped`, so they come back after a reboot once
the Docker service starts. More incident guidance: [RUNBOOK.md](RUNBOOK.md).

## 8. Known limits of a single-instance deployment

* One machine is a single point of failure; a reboot or instance failure means downtime.
* Uploaded files live on that machine's disk; running several API instances would
  need shared storage (EFS) or object storage (S3) first.
* Uploads are processed while the request waits; very large batches are bounded by
  `MAX_BATCH_FILES` rather than handled by a background queue.

Next steps when traffic grows: RDS for PostgreSQL, ElastiCache for Redis, S3 for
resumes, an ALB in front of an Auto Scaling group (or ECS/EKS using `k8s/`).
