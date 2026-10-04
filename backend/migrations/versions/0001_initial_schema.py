"""initial schema: documents, chunks, vector + full-text indexes

Revision ID: 0001
Revises:
Create Date: 2026-10-04
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute("""
        CREATE TABLE documents (
            id          BIGSERIAL PRIMARY KEY,
            filename    TEXT        NOT NULL,
            file_type   TEXT        NOT NULL,
            status      TEXT        NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'indexed', 'failed')),
            error       TEXT,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute("""
        CREATE TABLE chunks (
            id           BIGSERIAL PRIMARY KEY,
            document_id  BIGINT  NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            chunk_index  INTEGER NOT NULL,
            text         TEXT    NOT NULL,
            heading      TEXT,
            page         INTEGER,
            source       TEXT    NOT NULL,
            embedding    vector(384),
            tsv          tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED,
            UNIQUE (document_id, chunk_index)
        )
    """)

    op.execute("CREATE INDEX chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops)")
    op.execute("CREATE INDEX chunks_tsv_gin ON chunks USING gin (tsv)")
    op.execute("CREATE INDEX chunks_document_id_idx ON chunks (document_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS chunks")
    op.execute("DROP TABLE IF EXISTS documents")
    # The vector extension is left installed: it may be shared with other databases' objects.
