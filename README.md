# Ad Redirector

Direct-link redirector for [JuicyAds](https://www.juicyads.com/) code IDs. You register a JuicyAds code ID, get a shareable link, and every visit to that link is counted, logged (IP + time) and redirected to the JuicyAds ad endpoint for that code.

Stack: Django 6.1, PostgreSQL 17, Celery with Redis, gunicorn, Poetry.

## Quick start

```bash
./make.sh setup           # first time; on the server: ./make.sh setup --prod
```

This creates `.env` with random passwords, starts every container, downloads the GeoIP and Tor data, and writes usernames, passwords and URLs to `credentials.txt` (git-ignored). Locally, add `127.0.0.1 adredirector.loc` to your hosts file.

| Command | What it does |
|---|---|
| `./make.sh setup [--prod]` | First-time setup (see above) |
| `./make.sh deploy [--build]` | Daily deployment: `git pull` and restart the Django and Celery containers (migrations run on start). Rebuilds the image only when `Dockerfile`, `pyproject.toml` or `poetry.lock` changed, or with `--build` |
| `./make.sh build [args]` | `docker compose build`, e.g. `./make.sh build --no-cache` |

Details in [docs/docker.md](docs/docker.md).

## Documentation

- [Docker](docs/docker.md): services, running locally with Docker, pgAdmin
- [Project structure](docs/project-structure.md): where the code lives
- [How it works](docs/how-it-works.md): links, redirects, clicks, GeoIP and Tor downloads
- [Traffic filtering](docs/traffic-filtering.md): the filters that keep low-quality traffic away from JuicyAds
- [Deploy to production](docs/production.md): HTTPS with nginx-proxy and Let's Encrypt
- [Local development without Docker](docs/local-development.md): Poetry, SQLite, tests
- [Configuration](docs/configuration.md): every `.env` setting
