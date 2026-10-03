FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=1.8.5 \
    POETRY_VIRTUALENVS_CREATE=false \
    POETRY_NO_INTERACTION=1 \
    DJANGO_STATIC_ROOT=/srv/static \
    MAXMIND_DATABASE_DIR=/srv/geoip

WORKDIR /app

RUN pip install --no-cache-dir "poetry==$POETRY_VERSION"

# Only the dependencies are installed in the image. The project code is mounted at /app
# by docker-compose.yml, so code changes don't need a rebuild; only dependency changes do.
COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root && rm -rf /root/.cache

RUN useradd --system --no-create-home app \
    && mkdir -p /srv/geoip /srv/static && chown app /srv/geoip /srv/static

USER app
EXPOSE 8000

ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--access-logfile", "-"]
