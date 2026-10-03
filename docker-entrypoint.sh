#!/bin/sh
set -e

# Only the web service runs setup; celery-worker/celery-beat set RUN_MIGRATIONS=0.
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    python manage.py migrate --noinput

    # Create the admin account on first start if DJANGO_SUPERUSER_* is set.
    if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
        python manage.py createsuperuser --noinput --email "${DJANGO_SUPERUSER_EMAIL:-admin@example.com}" 2>/dev/null \
            && echo "Created superuser $DJANGO_SUPERUSER_USERNAME" \
            || echo "Superuser $DJANGO_SUPERUSER_USERNAME already exists"
    fi
fi

exec "$@"
