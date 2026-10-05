import psycopg
import pytest
import sqlalchemy.exc

from app import ratelimit
from app.db import migrate


@pytest.fixture(autouse=True)
def _fresh_rate_limits():
    ratelimit.reset()
    yield
    ratelimit.reset()


@pytest.fixture(scope="session")
def db_ready():
    """Migrate the dev database, or skip the test when Postgres isn't reachable."""
    try:
        migrate()
    except (psycopg.OperationalError, sqlalchemy.exc.OperationalError) as exc:
        pytest.skip(f"Postgres not available: {exc}")
