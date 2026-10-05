"""answer_cache: exact and semantic cache of answered questions

`scope` fingerprints everything that shapes an answer (model, prompt, retrieval settings); `corpus` fingerprints the
document set. A change to either simply stops matching old rows, so stale answers are never served.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-05
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE answer_cache (
            id           BIGSERIAL PRIMARY KEY,
            scope        TEXT        NOT NULL,
            corpus       TEXT        NOT NULL,
            key_hash     TEXT        NOT NULL,
            embedding    vector(1024) NOT NULL,
            answer       JSONB       NOT NULL,
            hits         INTEGER     NOT NULL DEFAULT 0,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_hit_at  TIMESTAMPTZ,
            UNIQUE (scope, corpus, key_hash)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS answer_cache")
