# Docker

## Services

| Service | Container | URL on your machine | What it is |
|---|---|---|---|
| `web` | `ad-redirector-web` | `http://adredirector.loc:8000` (port set by `WEB_PORT`) | Django app: `runserver` locally, gunicorn in production |
| `celery-worker` | `ad-redirector-celery-worker` | — | Celery worker that runs background tasks; stores the MaxMind databases and Tor list in the `ad_redirector_geoip_data` volume, which `web` reads |
| `celery-beat` | `ad-redirector-celery-beat` | — | Celery beat, queues periodic tasks from `CELERY_BEAT_SCHEDULE` |
| `redis` | `ad-redirector-redis` | — | Message broker for Celery |
| `db` | `ad-redirector-db` | — | PostgreSQL |
| `pgadmin` | `ad-redirector-pgadmin` | `http://localhost:5050` | pgAdmin for `db` |

Every container is named with an `ad-redirector-` prefix and joins the external Docker network `ad-redirector-network`. Create it once before the first start:

```bash
docker network create ad-redirector-network
```

Each container keeps at most 3 log files of 5 MB each.

Requires Docker with Compose. On WSL, enable your distro in Docker Desktop → Settings → Resources → WSL Integration.

## Run with Docker

From the project root, after creating the network (see [Services](#services)):

Add the local domain to your hosts file (on WSL with a Windows browser: `C:\Windows\System32\drivers\etc\hosts`, edited as administrator):

```
127.0.0.1 adredirector.loc
```

```bash
cp .env.example .env      # then edit the secrets in .env
docker compose up --build
```

Open `http://adredirector.loc:8000/privateplace/` and log in with `DJANGO_SUPERUSER_USERNAME` / `DJANGO_SUPERUSER_PASSWORD` from `.env`.

pgAdmin runs at `http://localhost:5050`; log in with `PGADMIN_DEFAULT_EMAIL` / `PGADMIN_DEFAULT_PASSWORD` from `.env`. The server *ad-redirector (Django)* is already listed; when you open it, enter `POSTGRES_PASSWORD`. It is registered with the username `ad_redirector`, so if you change `POSTGRES_USER`, also change `Username` in `docker/pgadmin/servers.json`. That file is only read when pgAdmin starts with an empty `ad_redirector_pgadmin_data` volume.

How the Django container runs:

1. **Build:** the image starts from `python:3.12-slim` and installs the locked dependencies with Poetry. It contains no project code: `web`, `celery-worker` and `celery-beat` mount the project folder at `/app`, locally and in production. Rebuild only after changing `Dockerfile`, `pyproject.toml` or `poetry.lock`.
2. **Start:** Compose starts `web` only after PostgreSQL passes its health check. `docker-entrypoint.sh` then applies migrations, runs `collectstatic` so the admin's CSS/JS are ready, and creates the admin account if it doesn't exist yet.
3. **Serve:** locally, Django's `runserver` serves the app on port 8000 and reloads when code changes; `celery-worker` and `celery-beat` run under `watchfiles`, which restarts them when a `.py` file changes. In production (`docker-compose.prod.yml`), gunicorn runs the app (`config.wsgi`) with 3 worker processes and Celery runs without auto-restart; `./make.sh deploy` restarts them after pulling new code. WhiteNoise serves the static files in both cases.

Data is kept in the `ad_redirector_db_data` volume and pgAdmin's settings in `ad_redirector_pgadmin_data`. To wipe both: `docker compose down -v`.
