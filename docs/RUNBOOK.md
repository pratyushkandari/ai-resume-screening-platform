# Operations runbook

Production runs on AWS EC2 with Docker Compose; setup, HTTPS, updates and backups
are in [DEPLOYMENT.md](DEPLOYMENT.md). This page covers configuration and incidents.

## Configuration checklist (production)

| Variable | Required | Notes |
|---|---|---|
| `APP_ENV=production` | yes | Enables fail-fast checks and model-required readiness |
| `DATABASE_URL` | yes | `postgresql+psycopg2://user:pass@host:5432/db` (`postgresql://` is also accepted) |
| `JWT_SECRET_KEY` | yes | Random, ≥ 32 chars; rotating it signs everyone out |
| `HR_SIGNUP_CODE` | no | Empty disables recruiter self-registration |
| `REDIS_URL` | no | Enables shared summary cache and rate-limit counters |
| `CORS_ORIGINS` | yes, if the UI is on another origin | Comma-separated |
| `UPLOAD_DIR` | yes | Persistent (and shared across replicas) storage |
| `FORWARDED_ALLOW_IPS` | set in the image | Proxies allowed to set the client IP (default: private networks). Never `*` |

Numeric settings (`MAX_UPLOAD_MB`, `MAX_BATCH_FILES`, `ACCESS_TOKEN_EXPIRE_MINUTES`,
`SUMMARY_CACHE_TTL_SECONDS`, rate limits) are validated at start-up; an invalid value
stops the process with a message naming the variable.

## Start / stop

```bash
docker compose up --build -d      # start
docker compose logs -f backend    # follow API logs
docker compose down               # stop (volumes pgdata/uploads are kept)
```

Local without Docker: see the README quick start.

## Accounts

```bash
cd backend
python manage.py create-user --name "Jane Recruiter" --email jane@acme.com --role hr
python manage.py reset-password --email jane@acme.com
```
(In Docker: `docker compose exec backend python manage.py ...`.)
Accounts created by versions before 3.0 that still have plaintext passwords can no
longer sign in; reset their password with the command above.

## Health signals

| Check | Healthy | If not |
|---|---|---|
| `GET /healthz` | 200 | Process down: check container logs / restarts |
| `GET /readyz` `database` | `connected` | Check `DATABASE_URL`, network, `pg_isready -h <host>`. `schema not ready` means the tables could not be created yet; it retries on every check |
| `GET /readyz` `ml_model` | `active` | Model missing: image built with `PRELOAD_MODEL=0`, no network to Hugging Face, or out of memory. Scores are neutral until fixed; run **Evaluate** afterwards to backfill embeddings |
| `GET /readyz` `cache` | `redis` | Optional; without Redis the summary is recomputed per request and rate limits are per process |
| `/metrics` 5xx share | ~0 | Look up `X-Request-ID` in the logs |

## Common incidents

**Uploads fail with 413 from Nginx** — `client_max_body_size` in `frontend/nginx.conf`
must be at least `MAX_BATCH_FILES × MAX_UPLOAD_MB`.

**Users are signed out after a deploy** — `JWT_SECRET_KEY` changed (or was unset
in development, where a random key is generated per process).

**429 Too Many Requests on login** — the per-IP limit
(`LOGIN_RATE_LIMIT_PER_MINUTE`) was hit; it resets within a minute. If *all* users
are limited together, the API sees the proxy's IP instead of the client's: Uvicorn
must run with `--proxy-headers` and the proxy's address must be inside
`FORWARDED_ALLOW_IPS` (private networks by default).

**A user reports an error with a request ID** — search the API logs for that ID;
the full traceback is logged next to it.

**Downloads return 404 "file not found on server storage"** — the database row
exists but the file is gone: the upload volume was not persisted or not shared
between replicas.

## Backups

```bash
pg_dump -Fc -f resume_db_$(date +%Y%m%d).dump "$DATABASE_URL"
pg_restore -d "$DATABASE_URL" --clean resume_db_YYYYMMDD.dump
```
Back up `UPLOAD_DIR` together with the database; rows reference files by name.

## Schema

`sql/seed.sql` is idempotent (`CREATE TABLE IF NOT EXISTS`) and safe to re-run.
The API also creates missing tables at start-up. Changing existing columns needs a
migration tool (e.g. Alembic), which this project does not include yet.
