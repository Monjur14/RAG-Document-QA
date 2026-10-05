"""security layers: quarantine + scan flags on chunks, and a 'blocked' request status

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-05
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_OLD = "('answered', 'insufficient_evidence', 'model_declined', 'uncited', 'error')"
_NEW = "('answered', 'insufficient_evidence', 'model_declined', 'uncited', 'blocked', 'error')"


def upgrade() -> None:
    op.execute("ALTER TABLE chunks ADD COLUMN flags TEXT[] NOT NULL DEFAULT '{}'")
    op.execute("ALTER TABLE chunks ADD COLUMN quarantined BOOLEAN NOT NULL DEFAULT false")
    op.execute("ALTER TABLE request_log DROP CONSTRAINT IF EXISTS request_log_status_check")
    op.execute(f"ALTER TABLE request_log ADD CONSTRAINT request_log_status_check CHECK (status IN {_NEW})")


def downgrade() -> None:
    op.execute("DELETE FROM request_log WHERE status = 'blocked'")
    op.execute("ALTER TABLE request_log DROP CONSTRAINT IF EXISTS request_log_status_check")
    op.execute(f"ALTER TABLE request_log ADD CONSTRAINT request_log_status_check CHECK (status IN {_OLD})")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS quarantined")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS flags")
