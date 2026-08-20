#!/usr/bin/env sh
set -eu

: "${DATABASE_URL:?DATABASE_URL must be configured for the production API}"
: "${SECRET_KEY:?SECRET_KEY must be configured for the production API}"

echo "Applying Alembic migrations..."
alembic upgrade head

echo "Starting Dietary Recommendation API..."
exec "$@"
