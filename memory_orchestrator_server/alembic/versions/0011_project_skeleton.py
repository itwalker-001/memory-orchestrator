"""project skeleton tables + api_tokens.project_id

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0011_project_skeleton"
down_revision = "0010_age_extension"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "project_skeleton_nodes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("parent_id", UUID(as_uuid=True),
                  sa.ForeignKey("project_skeleton_nodes.id", ondelete="CASCADE"),
                  nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("prompt_hint", sa.Text(), nullable=False, server_default=""),
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_psn_parent_id", "project_skeleton_nodes", ["parent_id"])
    op.create_table(
        "skeleton_node_memories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("skeleton_node_id", UUID(as_uuid=True),
                  sa.ForeignKey("project_skeleton_nodes.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("memory_id", UUID(as_uuid=True),
                  sa.ForeignKey("memories.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.UniqueConstraint("skeleton_node_id", "memory_id", name="uq_snm_node_memory"),
    )
    op.create_index("ix_snm_memory_id", "skeleton_node_memories", ["memory_id"])
    op.add_column(
        "api_tokens",
        sa.Column("project_id", UUID(as_uuid=True),
                  sa.ForeignKey("projects.id", ondelete="SET NULL"),
                  nullable=True),
    )
    # Intentional: mcp_client tokens are replaced by project_token kind.
    # Existing mcp_client rows are invalid after this migration.
    op.execute("DELETE FROM api_tokens WHERE kind = 'mcp_client'")


def downgrade() -> None:
    op.drop_index("ix_snm_memory_id", table_name="skeleton_node_memories")
    op.drop_index("ix_psn_parent_id", table_name="project_skeleton_nodes")
    op.drop_column("api_tokens", "project_id")
    op.drop_table("skeleton_node_memories")
    op.drop_table("project_skeleton_nodes")
