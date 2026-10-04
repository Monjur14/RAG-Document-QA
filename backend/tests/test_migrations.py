"""Migrations run against a throwaway database, never your real one."""
import uuid

import psycopg
import pytest
from sqlalchemy.engine import make_url

from app.config import DATABASE_URL
from app.db import downgrade, migrate


@pytest.fixture()
def scratch_url():
    admin = make_url(DATABASE_URL)
    name = f"rag_migtest_{uuid.uuid4().hex[:8]}"
    try:
        admin_conn = psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True)
    except psycopg.OperationalError as exc:
        pytest.skip(f"Postgres not available: {exc}")
    admin_conn.execute(f'CREATE DATABASE "{name}"')
    try:
        yield admin.set(database=name).render_as_string(hide_password=False)
    finally:
        admin_conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')
        admin_conn.close()


def _tables(url: str) -> set[str]:
    with psycopg.connect(url) as c:
        rows = c.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'").fetchall()
    return {r[0] for r in rows}


def test_upgrade_downgrade_upgrade(scratch_url):
    migrate(scratch_url)
    assert {"documents", "chunks", "alembic_version"} <= _tables(scratch_url)

    migrate(scratch_url)  # running twice is a no-op
    downgrade(scratch_url)
    assert not {"documents", "chunks"} & _tables(scratch_url)

    migrate(scratch_url)  # recreates from scratch
    assert {"documents", "chunks"} <= _tables(scratch_url)
