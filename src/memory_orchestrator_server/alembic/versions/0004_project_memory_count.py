"""projects.memory_count denormalized counter

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-25
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("memory_count", sa.Integer(), nullable=False, server_default="0"))
    op.execute("""
        UPDATE projects p
        SET memory_count = (
            SELECT COUNT(*) FROM memories m
            WHERE m.project_id = p.id AND m.superseded_by IS NULL
        )
    """)


def downgrade() -> None:
    op.drop_column("projects", "memory_count")
