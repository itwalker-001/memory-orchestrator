"""add AGE graph extension

Revision ID: 0010_age_extension
Revises: 0009_api_token_enabled
Create Date: 2026-05-11
"""
from alembic import op

revision = "0010_age_extension"
down_revision = "0009_api_token_enabled"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS age")
    op.execute("LOAD 'age'")
    op.execute('SET search_path = ag_catalog, "$user", public')
    op.execute("SELECT create_graph('memory_graph')")


def downgrade() -> None:
    op.execute("LOAD 'age'")
    op.execute('SET search_path = ag_catalog, "$user", public')
    op.execute("SELECT drop_graph('memory_graph', true)")
    op.execute("DROP EXTENSION IF EXISTS age")
