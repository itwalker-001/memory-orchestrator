"""skeleton node tags column

Revision ID: 0012_skeleton_node_tags
Revises: 0011
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0012_skeleton_node_tags"
down_revision = "0011_project_skeleton"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "project_skeleton_nodes",
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text),
            server_default="{}",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("project_skeleton_nodes", "tags")
