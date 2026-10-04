"""Alembic environment. Migrations are plain SQL (no ORM models), so there is no autogenerate."""
from alembic import context
from sqlalchemy import create_engine

from app.config import DATABASE_URL

config = context.config


def _url() -> str:
    url = config.get_main_option("sqlalchemy.url") or DATABASE_URL
    # Our URL is a plain libpq URL; SQLAlchemy needs to be told to use psycopg 3.
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def run_migrations_offline() -> None:
    context.configure(url=_url(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url())
    with engine.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
