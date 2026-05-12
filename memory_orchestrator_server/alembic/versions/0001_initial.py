"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-21
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "projects",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("root_paths", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "memories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("why", sa.Text()),
        sa.Column("how_to_apply", sa.Text()),
        sa.Column("embedding", Vector(512)),
        sa.Column("importance", sa.SmallInteger(), nullable=False, server_default="3"),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_hit_at", sa.DateTime(timezone=True)),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("superseded_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("memories.id")),
    )
    op.create_index(
        "memories_project_type_idx",
        "memories",
        ["project_id", "type"],
        postgresql_where=sa.text("superseded_by IS NULL"),
    )
    op.execute(
        "CREATE INDEX memories_embedding_idx ON memories "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "sessions",
        sa.Column("session_id", sa.Text(), primary_key=True),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column("last_ingested_at", sa.DateTime(timezone=True)),
        sa.Column("last_offset", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("last_error", sa.Text()),
    )


def downgrade() -> None:
    op.drop_table("sessions")
    op.execute("DROP INDEX IF EXISTS memories_embedding_idx")
    op.drop_index("memories_project_type_idx", table_name="memories")
    op.drop_table("memories")
    op.drop_table("projects")
