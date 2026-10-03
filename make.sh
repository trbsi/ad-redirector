#!/usr/bin/env bash
# Project tasks. Run ./make.sh without arguments for help.
set -euo pipefail

cd "$(dirname "$0")"

NETWORK=ad-redirector-network
CREDENTIALS_FILE=credentials.txt
APP_SERVICES=(web celery-worker celery-beat)

usage() {
    cat <<'EOF'
Usage: ./make.sh <command> [options]

Commands:
  setup [--prod]   First-time setup: creates .env with random passwords, the Docker network,
                   builds and starts every container, downloads the GeoIP databases and Tor list,
                   and writes usernames, passwords and URLs to credentials.txt.
                   --prod also asks for the domain and Let's Encrypt email and enables
                   docker-compose.prod.yml (HTTPS via nginx-proxy).
  deploy [--build] Daily deployment: pulls the latest code and restarts the Django and Celery
                   containers (migrations and collectstatic run on start). The code is mounted, so
                   the image is only rebuilt when Dockerfile, pyproject.toml or poetry.lock changed,
                   or with --build.
  build [args]     Builds the Docker images; extra arguments go to "docker compose build",
                   e.g. ./make.sh build --no-cache
EOF
}

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31mError:\033[0m %s\n' "$*" >&2; exit 1; }

require_docker() {
    command -v docker >/dev/null || fail "docker is not installed"
    docker compose version >/dev/null 2>&1 || fail "the docker compose plugin is not installed"
}

random_secret() {
    # Letters and digits only, so the value is safe in .env and in sed.
    LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c "${1:-32}" || true
}

env_get() {
    grep -E "^$1=" .env | tail -n 1 | cut -d= -f2- || true
}

env_set() {
    if grep -qE "^$1=" .env; then
        sed -i "s|^$1=.*|$1=$2|" .env
    else
        printf '%s=%s\n' "$1" "$2" >>.env
    fi
}

is_placeholder() {
    [[ -z "$1" || "$1" == change-me* ]]
}

# Replaces a "change-me" placeholder in .env with a random value.
generate_secret() {
    local key=$1 length=${2:-32}
    if is_placeholder "$(env_get "$key")"; then
        env_set "$key" "$(random_secret "$length")"
        info "Generated $key"
    fi
}

generate_secret_for_new_volume() {
    local volume=$1 key=$2 length=$3
    if docker volume inspect "$volume" >/dev/null 2>&1; then
        is_placeholder "$(env_get "$key")" &&
            info "Keeping $key: volume $volume already exists with this value"
        return 0
    fi
    generate_secret "$key" "$length"
}

ask() {
    # ask KEY "Question" [default] — keeps an existing value, otherwise prompts.
    local key=$1 question=$2 default=${3:-} current answer
    current=$(env_get "$key")
    if [[ -n "$current" ]]; then
        return
    fi
    # No terminal (e.g. run from CI): leave the value empty.
    read -rp "$question${default:+ [$default]}: " answer || true
    env_set "$key" "${answer:-$default}"
}

setup() {
    local prod=0
    [[ "${1:-}" == "--prod" ]] && prod=1
    require_docker

    if [[ ! -f .env ]]; then
        cp .env.example .env
        info "Created .env from .env.example"
    fi

    generate_secret DJANGO_SECRET_KEY 50
    # These are only applied the first time their volume is created, so once the volume
    # exists the value in .env is the one in use and must not change.
    generate_secret_for_new_volume ad_redirector_db_data POSTGRES_PASSWORD 32
    generate_secret_for_new_volume ad_redirector_db_data DJANGO_SUPERUSER_PASSWORD 20
    generate_secret_for_new_volume ad_redirector_pgadmin_data PGADMIN_DEFAULT_PASSWORD 20

    if ((prod)); then
        ask DOMAIN "Public domain (DNS must point to this server)"
        ask LETSENCRYPT_EMAIL "Email for Let's Encrypt notices"
        local domain
        domain=$(env_get DOMAIN)
        [[ -n "$domain" ]] || fail "DOMAIN is required for --prod"
        env_set DJANGO_ALLOWED_HOSTS "$domain"
        env_set DJANGO_CSRF_TRUSTED_ORIGINS "https://$domain"
        env_set DJANGO_DEBUG 0
        # Makes every plain "docker compose" command include the production file.
        env_set COMPOSE_FILE "docker-compose.yml:docker-compose.prod.yml"
    fi

    ask MAXMIND_ACCOUNT_ID "MaxMind account ID (Enter to skip)"
    ask MAXMIND_LICENSE_KEY "MaxMind license key (Enter to skip)"

    if ! docker network inspect "$NETWORK" >/dev/null 2>&1; then
        docker network create "$NETWORK" >/dev/null
        info "Created Docker network $NETWORK"
    fi

    info "Building and starting containers"
    docker compose up -d --build --wait

    info "Downloading the Tor exit node list"
    docker compose exec -T celery-worker python manage.py download_tor_exit_nodes ||
        info "Tor download failed; the hourly task will retry"
    if [[ -n "$(env_get MAXMIND_ACCOUNT_ID)" && -n "$(env_get MAXMIND_LICENSE_KEY)" ]]; then
        info "Downloading the MaxMind databases"
        docker compose exec -T celery-worker python manage.py download_geoip_database ||
            info "MaxMind download failed; the daily task will retry"
    else
        info "Skipping MaxMind download: set MAXMIND_ACCOUNT_ID and MAXMIND_LICENSE_KEY in .env"
    fi

    write_credentials "$prod"
    info "Done. Usernames, passwords and URLs are in $CREDENTIALS_FILE"
}

write_credentials() {
    local prod=$1 site pgadmin
    # A server set up earlier with --prod keeps COMPOSE_FILE pointing at the production file.
    [[ "$(env_get COMPOSE_FILE)" == *docker-compose.prod.yml* ]] && prod=1
    if ((prod)); then
        site="https://$(env_get DOMAIN)"
        pgadmin="http://$(env_get DOMAIN):5050"
    else
        local port
        port=$(env_get WEB_PORT)
        site="http://adredirector.loc:${port:-8000}"
        pgadmin="http://localhost:5050"
    fi

    umask 077
    cat >"$CREDENTIALS_FILE" <<EOF
Ad Redirector credentials, generated $(date '+%Y-%m-%d %H:%M')
Keep this file private. It is git-ignored.

Site
  URL:       $site/
  Link URLs: $site/go/<code>/

Django admin
  URL:       $site/privateplace/
  Username:  $(env_get DJANGO_SUPERUSER_USERNAME)
  Password:  $(env_get DJANGO_SUPERUSER_PASSWORD)

pgAdmin
  URL:       $pgadmin
  Email:     $(env_get PGADMIN_DEFAULT_EMAIL)
  Password:  $(env_get PGADMIN_DEFAULT_PASSWORD)

PostgreSQL (enter this password when pgAdmin asks for it)
  Host:      db (inside Docker)
  Database:  $(env_get POSTGRES_DB)
  Username:  $(env_get POSTGRES_USER)
  Password:  $(env_get POSTGRES_PASSWORD)
EOF
    if ((!prod)); then
        cat >>"$CREDENTIALS_FILE" <<'EOF'

Local domain: add this line to your hosts file
(WSL with a Windows browser: C:\Windows\System32\drivers\etc\hosts)
  127.0.0.1 adredirector.loc
EOF
    fi
}

deploy() {
    require_docker
    [[ -f .env ]] || fail ".env not found; run ./make.sh setup first"

    local rebuild=0
    [[ "${1:-}" == "--build" ]] && rebuild=1

    if git rev-parse --is-inside-work-tree >/dev/null 2>&1 && git remote | grep -q .; then
        local before
        before=$(git rev-parse HEAD)
        info "Pulling the latest code"
        git pull --ff-only
        if [[ -n "$(git diff --name-only "$before" HEAD -- Dockerfile pyproject.toml poetry.lock)" ]]; then
            info "Dependencies or Dockerfile changed"
            rebuild=1
        fi
    fi

    if ((rebuild)); then
        info "Rebuilding the image and recreating ${APP_SERVICES[*]}"
        docker compose build "${APP_SERVICES[@]}"
        docker compose up -d --force-recreate --wait "${APP_SERVICES[@]}"
        docker image prune -f >/dev/null
    else
        info "Restarting ${APP_SERVICES[*]}"
        docker compose up -d --wait "${APP_SERVICES[@]}"
        docker compose restart "${APP_SERVICES[@]}"
    fi

    docker compose ps
}

build() {
    require_docker
    docker compose build "$@"
}

command=${1:-}
shift || true
case "$command" in
    setup) setup "$@" ;;
    deploy) deploy "$@" ;;
    build) build "$@" ;;
    "" | -h | --help | help) usage ;;
    *) usage; exit 1 ;;
esac
