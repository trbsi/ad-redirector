# Configuration

Set in `.env` (see [`.env.example`](../.env.example)):

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_SECRET_KEY` | — (required unless `DJANGO_DEBUG=1`) | Django secret key |
| `DJANGO_DEBUG` | `0` | Debug mode |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,adredirector.loc` | Comma-separated hostnames the app answers to |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | empty | Needed for admin login on a real domain, e.g. `https://links.example.com` |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | `ad_redirector` / `ad_redirector` / — | Database credentials |
| `POSTGRES_HOST`, `POSTGRES_PORT` | set by Compose / `5432` | Database server; if `POSTGRES_HOST` is unset, SQLite is used |
| `DJANGO_SUPERUSER_USERNAME` / `_PASSWORD` / `_EMAIL` | — | Admin account created on container start |
| `PGADMIN_DEFAULT_EMAIL` / `PGADMIN_DEFAULT_PASSWORD` | `admin@example.com` / — (required) | pgAdmin login |
| `CELERY_BROKER_URL` | `redis://localhost:6379/0` (Compose sets `redis://redis:6379/0`) | Celery broker |
| `MAXMIND_ACCOUNT_ID` / `MAXMIND_LICENSE_KEY` | — | MaxMind credentials for the daily database download |
| `MAXMIND_EDITION_IDS` | `GeoLite2-Country,GeoLite2-ASN` | Databases to download; add `GeoIP2-Anonymous-IP` (paid) for the VPN/proxy filter |
| `MAXMIND_DATABASE_DIR` | `/srv/geoip` in Docker, `geoip/` locally | Where the `.mmdb` files and the Tor exit node list are stored |
| `TRAFFIC_FILTER_LOG_ONLY` | `0` | `1` = record what would be blocked, but block nothing |
| `TRAFFIC_FILTER_BLOCKED_URL` | `/` | Where blocked visits are sent |
| `TRAFFIC_FILTER_ALLOWED_COUNTRIES` | empty (all allowed) | Comma-separated ISO country codes to allow, e.g. `US,GB,DE` |
| `TRAFFIC_FILTER_BLOCKED_COUNTRIES` | empty | Comma-separated ISO country codes to block |
| `TRAFFIC_FILTER_EXTRA_BLOCKED_ASNS` | empty | ASNs to block on top of the built-in hosting provider list |
| `TRAFFIC_FILTER_REPEAT_CLICK_HOURS` | `24` | Block repeat visits from one IP to one link within this many hours; `0` = off |
| `TRAFFIC_FILTER_CHALLENGE` | `1` | JavaScript check page before redirecting; `0` = off |
| `DOMAIN` / `LETSENCRYPT_EMAIL` | — (required in production) | Public domain and Let's Encrypt contact email for `docker-compose.prod.yml` |
| `WEB_PORT` | `8000` | Local only: host port the `web` container is published on |
| `USE_X_FORWARDED_FOR` | `0` | Log the last `X-Forwarded-For` entry, the address your proxy saw. Enable only behind exactly one reverse proxy you control (set automatically in production), otherwise visitors can fake their IP |
| `JUICYADS_REDIRECT_URL` | built-in JuicyAds URL (see `config/settings.py`) | Redirect target; `{code}` is replaced with the URL-encoded code ID |
