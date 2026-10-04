"""switch embedding column to 1024 dimensions (bge-large-en-v1.5)

Vectors from different models are not comparable and cannot be converted, so this migration
DELETES all documents and chunks (they must be re-uploaded). Acceptable while the project has
only test data; do not reuse this pattern on real data without a re-index step.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-04
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _resize(dim: int) -> None:
    op.execute("DROP INDEX IF EXISTS chunks_embedding_hnsw")
    op.execute("DELETE FROM chunks")
    op.execute("DELETE FROM documents")
    op.execute(f"ALTER TABLE chunks ALTER COLUMN embedding TYPE vector({dim})")
    op.execute("CREATE INDEX chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops)")


def upgrade() -> None:
    _resize(1024)


def downgrade() -> None:
    _resize(384)
