"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from pgvector.sqlalchemy import Vector

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

_EMBED_DIM = 1024


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.create_table(
        "projects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("slug", sa.Text(), nullable=False, unique=True),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("root_paths", ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("memory_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "memories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("why", sa.Text()),
        sa.Column("how_to_apply", sa.Text()),
        sa.Column("embedding", Vector(_EMBED_DIM)),
        sa.Column("importance", sa.SmallInteger(), nullable=False, server_default="3"),
        sa.Column("hit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_hit_at", sa.DateTime(timezone=True)),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_client", sa.Text(), nullable=False, server_default="claude"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("superseded_by", UUID(as_uuid=True), sa.ForeignKey("memories.id")),
    )
    op.create_index("ix_memories_project_id", "memories", ["project_id"])
    op.create_index(
        "memories_project_type_idx", "memories", ["project_id", "type"],
        postgresql_where=sa.text("superseded_by IS NULL"),
    )
    op.execute(
        "CREATE INDEX memories_embedding_idx ON memories "
        "USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "system_settings",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "api_tokens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("owner_user", sa.Text()),
        sa.Column("scopes", ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "sessions",
        sa.Column("session_id", sa.Text(), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("last_ingested_at", sa.DateTime(timezone=True)),
        sa.Column("last_offset", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("last_error", sa.Text()),
    )

    op.create_table(
        "project_skeleton_nodes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("parent_id", UUID(as_uuid=True),
                  sa.ForeignKey("project_skeleton_nodes.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("prompt_hint", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tags", ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_psn_project_id", "project_skeleton_nodes", ["project_id"])
    op.create_index("ix_psn_parent_id", "project_skeleton_nodes", ["parent_id"])

    op.create_table(
        "skeleton_node_memories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("skeleton_node_id", UUID(as_uuid=True),
                  sa.ForeignKey("project_skeleton_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("memory_id", UUID(as_uuid=True),
                  sa.ForeignKey("memories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("skeleton_node_id", "memory_id", name="uq_snm_node_memory"),
    )
    op.create_index("ix_snm_memory_id", "skeleton_node_memories", ["memory_id"])


def downgrade() -> None:
    op.drop_table("skeleton_node_memories")
    op.drop_index("ix_psn_parent_id", table_name="project_skeleton_nodes")
    op.drop_index("ix_psn_project_id", table_name="project_skeleton_nodes")
    op.drop_table("project_skeleton_nodes")
    op.drop_table("sessions")
    op.drop_table("api_tokens")
    op.drop_table("system_settings")
    op.execute("DROP INDEX IF EXISTS memories_embedding_idx")
    op.drop_index("memories_project_type_idx", table_name="memories")
    op.drop_index("ix_memories_project_id", table_name="memories")
    op.drop_table("memories")
    op.drop_table("projects")
