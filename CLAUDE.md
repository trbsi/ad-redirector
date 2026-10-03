# Ad Redirector

Django app that turns JuicyAds code IDs into shareable links (`/go/<code>/`). Each visit is filtered for low-quality traffic, logged as a `Click`, counted and redirected to JuicyAds. Stack: Django 6.1, PostgreSQL 17, Celery + Redis, Poetry, Docker Compose.

Human docs are in `docs/` (docker, project-structure, how-it-works, traffic-filtering, production, local-development, configuration). Read the relevant one before changing that area, and update it when behavior or settings change.

## Code conventions

- One Django app: `src/redirect` (imported as `src.redirect`, app label `redirect`, URL namespace `redirect`).
- **Business logic lives in `src/redirect/services/`, not in views, tasks or commands.** Views only apply decorators, call a service and return a response. Celery tasks (`tasks.py`) and management commands are thin wrappers around services too.
- **Each service gets its own subfolder, and the file is named after its class in snake_case**: `services/redirect/redirect_service.py` → `RedirectService`. The folder's `__init__.py` re-exports the class (`from .redirect_service import RedirectService`), and callers import from the folder.
- **Exception: `services/filtering/` is flat.** Every filter is `filtering/<name>_filter_service.py` directly in that folder, with no subfolders. Shared helpers there are `geoip.py` (cached MaxMind readers) and `visit.py` (`Visit` dataclass).
- A traffic filter is a class with `reason = "<slug>"`, `__init__(self, visit)` and `matches() -> bool`. Register it in the `FILTERS` tuple in `filtering/__init__.py`; order matters (the first match decides `Click.blocked_reason`), cheap checks first. If a filter's data (MaxMind database, Tor list) is missing, it must let the visit through, not block it.
- New settings are read from env vars in `config/settings.py` (use the `env_bool` / `env_list` helpers) and documented in `.env.example` and `docs/configuration.md`.
- Visitor-facing pages extend `templates/redirect/base.html`, whose footer has the privacy link and the MaxMind GeoLite2 attribution (license requirement; the admin has it in `templates/admin/base_site.html`).
- **Personal data (GDPR):** IPs are personal data, and the clicks are on adult ads, so store as little as possible. Match visitors by `Click.ip_hash` (`hash_ip()` in `models.py`), never by the full `ip`, which is cleared after `CLICK_IP_RETENTION_DAYS`. Any new stored visitor data needs a retention rule in `services/clean_up_clicks/` and a line on the privacy page (`templates/redirect/privacy.html`). The hash is keyed with `DJANGO_SECRET_KEY`, so it is **pseudonymous, not anonymous** (whoever has the key can hash all IPv4 addresses and match). Proposed but not decided yet: a daily rotating hash key and not storing the full IP at all. Don't describe stored IPs as anonymous.

## Commands

```bash
DJANGO_DEBUG=1 poetry run python manage.py test             # tests (SQLite, no Docker needed)
DJANGO_DEBUG=1 poetry run python manage.py makemigrations    # after model changes
docker compose exec celery-worker python manage.py download_geoip_database
docker compose exec celery-worker python manage.py download_tor_exit_nodes
docker compose exec celery-worker python manage.py clean_up_clicks
docker compose exec db psql -U ad_redirector ad_redirector   # database shell, no password needed
./make.sh setup [--prod]   # first-time setup, writes credentials.txt (git-ignored)
./make.sh deploy [--build] # git pull + restart web/celery; rebuilds only if Dockerfile/pyproject.toml/poetry.lock changed
./make.sh build [args]     # docker compose build
```

- The virtualenv is `.venv/` (`.venv/bin/python` works directly). Add dependencies with `poetry add`, which updates `poetry.lock`.
- Outside Docker, Django does not read `.env`. Without `POSTGRES_HOST` it uses SQLite.
- To try a redirect by hand, use `curl -s -D - -o /dev/null http://adredirector.loc:8000/go/<code>/`. The views are GET-only, so `curl -I` (HEAD) returns 405. Plain curl counts as a bot: expect `302` with `Location: /`.
- Redirect tests send real-browser headers (`BROWSER`) and switch filters off with `@override_settings(**FILTERS_OFF)`. Otherwise the bot filter and the JavaScript check block the test client. GeoIP lookups are mocked by patching `...filtering.<name>_filter_service.reader`.

## Docker setup

- `docker-compose.yml` is the local setup; `docker-compose.prod.yml` is layered on top only on the server (via `COMPOSE_FILE` in the server's `.env`). It switches `web` to gunicorn, runs plain `celery`, and adds nginx-proxy + acme-companion (Let's Encrypt). It uses `!reset` / `!override` to remove or replace values from the base file.
- **Project code is mounted (`.:/app`) into `web`, `celery-worker` and `celery-beat`, locally and in production. It is never copied into the image.** The image only holds Python and the dependencies, so rebuild only when `Dockerfile`, `pyproject.toml` or `poetry.lock` change. After a dependency change, the containers must also be **recreated** (`docker compose up -d --build web celery-worker celery-beat`). A rebuilt image isn't used by running containers, which then fail with `ModuleNotFoundError` against the new mounted code. `docker-entrypoint.sh` runs `migrate` and `collectstatic` on `web` start (`RUN_MIGRATIONS=0` on the Celery containers).
- Locally: `runserver` reloads on code changes, and Celery runs under `watchfiles`, which restarts it when a `.py` file changes. No nginx locally.
- Local URL: `http://adredirector.loc:<WEB_PORT>` (default 8000; hosts entry `127.0.0.1 adredirector.loc`). Do not move the app to port 80. Admin is at `/privateplace/`, not `/admin/`. pgAdmin: `http://localhost:5050`.
- Compose project name `ad-redirector`; containers are named `ad-redirector-*`; volumes are named `ad_redirector_*`. The network `ad-redirector-network` is external (`docker network create ad-redirector-network`). Every service uses the shared log limit (3 × 5 MB).
- Celery beat schedule (`CELERY_BEAT_SCHEDULE` in settings, UTC): MaxMind databases (GeoLite2-Country, GeoLite2-ASN) daily at 03:00, Tor exit node list hourly at :15, `clean_up_clicks` daily at 04:00. Downloads go into the `ad_redirector_geoip_data` volume (`/srv/geoip`), which `web` mounts read-only.
- PostgreSQL: host `db`, port 5432, database and user `ad_redirector`, password `POSTGRES_PASSWORD` in `.env`. The port isn't published to the host, so connect through pgAdmin, `docker compose exec db psql`, or Django inside the containers.
- Behind nginx-proxy, `USE_X_FORWARDED_FOR=1` and the client IP is the **last** `X-Forwarded-For` entry (the one nginx-proxy appends). Don't switch it back to the first entry, because visitors can fake that one.

## Working with the user

- Ask before creating, recreating, restarting or removing Docker containers or volumes. Building images and throwaway `docker compose run --rm` checks are fine. Tell the user which command applies a change instead of running it.
- Never print secrets from `.env` or `credentials.txt`. Grep only the keys you need.
- The project was renamed from "alzir"; don't reintroduce that name. The legacy PHP app and the `/go.php` route were removed on purpose.
