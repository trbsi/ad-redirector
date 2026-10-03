# Ad Redirector

Direct-link redirector for [JuicyAds](https://www.juicyads.com/) code IDs. You register a JuicyAds code ID, get a shareable link, and every visit to that link is counted, logged (IP + time) and redirected to the JuicyAds ad endpoint for that code.

Stack: Django 6.1, PostgreSQL 17, Celery with Redis, gunicorn, Poetry.

## Docker services

| Service | Container | URL on your machine | What it is |
|---|---|---|---|
| `web` | `ad-redirector-web` | `http://localhost:8000` | Django app (gunicorn) |
| `celery-worker` | `ad-redirector-celery-worker` | — | Celery worker that runs background tasks; stores the MaxMind database in the `ad_redirector_geoip_data` volume |
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

---

### Layout

```
config/               Django settings, URLs, WSGI/ASGI
src/                  Django apps, imported with the src. prefix (e.g. "src.redirect")
  redirect/
    models.py         Link (code, visits, created_at) and Click (link, ip, target_url, created_at)
    views.py          Redirect view: /go/<code>/
    services/         Business logic, one subfolder per view or task (go/, download_geoip_database/) holding its service class
    tasks.py          Celery tasks
templates/admin/base_site.html   Admin footer with the MaxMind attribution
    admin.py          Admin for managing links and browsing clicks
    tests.py
Dockerfile, docker-compose.yml, docker-entrypoint.sh
docker/pgadmin/servers.json   pgAdmin's pre-registered connection to the db service
pyproject.toml, poetry.lock
.env.example
```

### How it works

- **Managing links:** log in to the Django admin at `/admin/` and add a link under *Links*. Codes must be lowercase letters and digits (e.g. `3484x2z2w2a4u4q2r28463o5111`) and must be unique. The list shows each link's visit count and its direct URL.
- **Redirecting:** `GET /go/<code>/` increments the link's visit count, records a `Click`, and returns a `302` to the JuicyAds URL. Unknown codes return `404`. Responses are sent with no-cache headers.
- **GeoIP database:** every day at 03:00 UTC, Celery beat queues `download_geoip_database`. It checks MaxMind's published SHA-256 first and only downloads when a new release is out, verifies the archive, and atomically replaces `<edition>.mmdb`. Run it immediately with `docker compose exec celery-worker celery -A config call src.redirect.tasks.download_geoip_database`. The GeoLite2 license requires the attribution shown in the admin footer.
- **Clicks:** browse and filter them under *Clicks* in the admin (read-only).

### Run with Docker

From the project root, after creating the network (see [Docker services](#docker-services)):

```bash
cp .env.example .env      # then edit the secrets in .env
docker compose up --build
```

Open `http://localhost:8000/admin/` and log in with `DJANGO_SUPERUSER_USERNAME` / `DJANGO_SUPERUSER_PASSWORD` from `.env`.

pgAdmin runs at `http://localhost:5050`; log in with `PGADMIN_DEFAULT_EMAIL` / `PGADMIN_DEFAULT_PASSWORD` from `.env`. The server *ad-redirector (Django)* is already listed; when you open it, enter `POSTGRES_PASSWORD`. It is registered with the username `ad_redirector`, so if you change `POSTGRES_USER`, also change `Username` in `docker/pgadmin/servers.json`. That file is only read when pgAdmin starts with an empty `ad_redirector_pgadmin_data` volume.

How the Django container runs:

1. **Build:** the image starts from `python:3.12-slim`, installs the locked dependencies with Poetry, copies the code and runs `collectstatic` so the admin's CSS/JS are ready.
2. **Start:** Compose starts `web` only after PostgreSQL passes its health check. `docker-entrypoint.sh` then applies migrations and creates the admin account if it doesn't exist yet.
3. **Serve:** gunicorn runs the app (`config.wsgi`) with 3 worker processes on port 8000. WhiteNoise serves the static files, so no separate web server is needed.

Data is kept in the `ad_redirector_db_data` volume and pgAdmin's settings in `ad_redirector_pgadmin_data`. To wipe both: `docker compose down -v`.

### Deploy to production (HTTPS)

`docker-compose.prod.yml` adds [nginx-proxy](https://github.com/nginx-proxy/nginx-proxy) (`ad-redirector-nginx-proxy`, ports 80/443) and [acme-companion](https://github.com/nginx-proxy/acme-companion) (`ad-redirector-acme-companion`), which gets a Let's Encrypt certificate for `DOMAIN` and renews it automatically. In this setup `web` is only reachable through nginx-proxy and logs the visitor IP that nginx-proxy appends to `X-Forwarded-For`. Local development doesn't use this file.

1. Point `DOMAIN`'s DNS at the server and open ports 80 and 443.
2. In `.env`, set `DOMAIN`, `LETSENCRYPT_EMAIL`, `DJANGO_ALLOWED_HOSTS=<domain>` and `DJANGO_CSRF_TRUSTED_ORIGINS=https://<domain>`.
3. Start everything with both files:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

To avoid typing both files, add `COMPOSE_FILE=docker-compose.yml:docker-compose.prod.yml` to the server's `.env`; plain `docker compose` commands then include production.

### Run locally without Docker

Requires Python 3.12+ and Poetry. Without `POSTGRES_HOST` set, the app uses a local SQLite file (`db.sqlite3`).

```bash
poetry install
export DJANGO_DEBUG=1
poetry run python manage.py migrate
poetry run python manage.py createsuperuser
poetry run python manage.py runserver
```

The virtualenv is created in `.venv/` (set by `poetry.toml`).

### Tests

```bash
DJANGO_DEBUG=1 poetry run python manage.py test
```

### Configuration

Set in `.env` (see [`.env.example`](.env.example)):

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | — (required unless `DJANGO_DEBUG=1`) | Django secret key |
| `DJANGO_DEBUG` | `0` | Debug mode |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated hostnames the app answers to |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | empty | Needed for admin login on a real domain, e.g. `https://links.example.com` |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | `ad_redirector` / `ad_redirector` / — | Database credentials |
| `POSTGRES_HOST`, `POSTGRES_PORT` | set by Compose / `5432` | Database server; if `POSTGRES_HOST` is unset, SQLite is used |
| `DJANGO_SUPERUSER_USERNAME` / `_PASSWORD` / `_EMAIL` | — | Admin account created on container start |
| `PGADMIN_DEFAULT_EMAIL` / `PGADMIN_DEFAULT_PASSWORD` | `admin@example.com` / — (required) | pgAdmin login |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` (Compose sets `redis://redis:6379/0`) | Celery broker |
| `MAXMIND_ACCOUNT_ID` / `MAXMIND_LICENSE_KEY` | — | MaxMind credentials for the daily GeoLite2 download |
| `MAXMIND_EDITION_ID` | `GeoLite2-City` | Which GeoLite2 database to download (e.g. `GeoLite2-Country`) |
| `MAXMIND_DATABASE_DIR` | `/srv/geoip` in Docker, `geoip/` locally | Where the `.mmdb` file is stored |
| `DOMAIN` / `LETSENCRYPT_EMAIL` | — (required in production) | Public domain and Let's Encrypt contact email for `docker-compose.prod.yml` |
| `USE_X_FORWARDED_FOR` | `0` | Log the last `X-Forwarded-For` entry, the address your proxy saw. Enable only behind exactly one reverse proxy you control (set automatically in production), otherwise visitors can fake their IP |
| `JUICYADS_REDIRECT_URL` | built-in JuicyAds URL (see `config/settings.py`) | Redirect target; `{code}` is replaced with the URL-encoded code ID |
