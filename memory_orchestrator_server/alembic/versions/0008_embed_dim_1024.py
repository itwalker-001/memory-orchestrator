"""Change embedding column to vector(1024) and add rerank system_settings

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-08
"""
from alembic import op

revision = "0008"
down_revision = "0007_api_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop HNSW index (required before altering column type)
    op.execute("DROP INDEX IF EXISTS memories_embedding_idx")

    # 2. Set all existing embeddings to NULL (512-dim vectors can't be cast to 1024-dim)
    op.execute("UPDATE memories SET embedding = NULL")

    # 3. Alter column to new dimension
    op.execute("ALTER TABLE memories ALTER COLUMN embedding TYPE vector(1024)")

    # 4. Recreate HNSW index for the new dimension
    op.execute(
        "CREATE INDEX memories_embedding_idx ON memories "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    # 5. Insert default system_settings (skip if already present)
    op.execute(
        """
        INSERT INTO system_settings (key, value, updated_at)
        VALUES
            ('embed_model', 'BAAI/bge-m3', now()),
            ('embed_dim', '1024', now()),
            ('rerank_enabled', 'true', now()),
            ('rerank_model', 'BAAI/bge-reranker-v2-m3', now())
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("UPDATE system_settings SET value = '512' WHERE key = 'embed_dim'")
    op.execute("DELETE FROM system_settings WHERE key IN ('rerank_enabled', 'rerank_model')")
    op.execute("DROP INDEX IF EXISTS memories_embedding_idx")
    op.execute("UPDATE memories SET embedding = NULL")
    op.execute("ALTER TABLE memories ALTER COLUMN embedding TYPE vector(512)")
    op.execute(
        "CREATE INDEX memories_embedding_idx ON memories "
        "USING hnsw (embedding vector_cosine_ops)"
    )
