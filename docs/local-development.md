# Local development without Docker

Requires Python 3.12+ and Poetry. Without `POSTGRES_HOST` set, the app uses a local SQLite file (`db.sqlite3`).

```bash
poetry install
export DJANGO_DEBUG=1
poetry run python manage.py migrate
poetry run python manage.py createsuperuser
poetry run python manage.py runserver
```

The virtualenv is created in `.venv/` (set by `poetry.toml`).

## Tests

```bash
DJANGO_DEBUG=1 poetry run python manage.py test
```
