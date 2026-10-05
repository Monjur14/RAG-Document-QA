#!/bin/sh
# Bring the database schema up to date, then start the server.
# Migrations are idempotent: on an up-to-date database this does nothing.
set -e
python -m app.db
exec "$@"
