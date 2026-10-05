"""request_log: one row per /ask request (tokens, cost, latency, cache status)

The question text is deliberately NOT stored: only its length. Logs hold no document or user content.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-05
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE request_log (
            id                 BIGSERIAL PRIMARY KEY,
            created_at         TIMESTAMPTZ      NOT NULL DEFAULT now(),
            status             TEXT             NOT NULL
                               CHECK (status IN ('answered', 'insufficient_evidence', 'model_declined', 'uncited', 'error')),
            cache              TEXT             NOT NULL DEFAULT 'miss' CHECK (cache IN ('miss', 'exact', 'semantic')),
            model              TEXT,
            prompt_tokens      INTEGER,
            completion_tokens  INTEGER,
            cost_usd           NUMERIC(12, 6)   NOT NULL DEFAULT 0,
            latency_ms         DOUBLE PRECISION NOT NULL,
            retrieved          INTEGER,
            confidence         REAL,
            question_chars     INTEGER          NOT NULL,
            error              TEXT
        )
    """)
    op.execute("CREATE INDEX request_log_created_at_idx ON request_log (created_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS request_log")
