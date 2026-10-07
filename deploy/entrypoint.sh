#!/bin/sh
set -e

echo "Waiting for database..."
python - <<'PY'
import os, time
import psycopg2

host = os.environ.get("POSTGRES_HOST", "db")
port = os.environ.get("POSTGRES_PORT", "5432")
name = os.environ.get("POSTGRES_DB", "ironman_db")
user = os.environ.get("POSTGRES_USER", "ironman_user")
password = os.environ.get("POSTGRES_PASSWORD", "")

for attempt in range(30):
    try:
        conn = psycopg2.connect(
            dbname=name,
            user=user,
            password=password,
            host=host,
            port=port,
        )
        conn.close()
        break
    except Exception:
        time.sleep(2)
else:
    raise SystemExit("Database did not become ready in time.")
PY

python manage.py migrate --noinput
python manage.py collectstatic --noinput

exec gunicorn ironman.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 60
