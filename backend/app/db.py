"""Database connection and migrations.

Schema changes are Alembic migrations in backend/migrations/versions/.
  python -m app.db          -> migrate to the latest version (same as `alembic upgrade head`)
"""
from pathlib import Path

import psycopg
from alembic import command
from alembic.config import Config
from pgvector.psycopg import register_vector

from app.config import DATABASE_URL

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def _alembic_config(url: str) -> Config:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))  # ConfigParser escapes %
    return cfg


def migrate(url: str = DATABASE_URL, revision: str = "head") -> None:
    """Bring the database to `revision` (default: latest). Safe to run repeatedly."""
    command.upgrade(_alembic_config(url), revision)


def downgrade(url: str = DATABASE_URL, revision: str = "base") -> None:
    """Roll back to `revision` (default: empty database). Destroys data."""
    command.downgrade(_alembic_config(url), revision)


def get_conn(url: str = DATABASE_URL) -> psycopg.Connection:
    """Open a connection that understands the pgvector type. Caller closes it."""
    conn = psycopg.connect(url)
    register_vector(conn)
    return conn


if __name__ == "__main__":
    migrate()
    print("Database is up to date.")
