"""add enabled flag to api_tokens

Revision ID: 0009_api_token_enabled
Revises: 0008
Create Date: 2026-05-09
"""
from alembic import op
import sqlalchemy as sa


revision = "0009_api_token_enabled"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_tokens",
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
    )


def downgrade() -> None:
    op.drop_column("api_tokens", "enabled")
