"""add pg_search extension and BM25 jieba index on memories

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-16
"""
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

BM25_INDEX = "memories_bm25_idx"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_search")
    # BM25 covering index: key_field 必须是第一列且有唯一索引（id 是主键，满足）。
    # name/description/content 三列各自用 jieba 中文分词；其余列不入索引（只做全文）。
    op.execute(
        f"CREATE INDEX IF NOT EXISTS {BM25_INDEX} ON memories "
        "USING bm25 (id, (name::pdb.jieba), (description::pdb.jieba), (content::pdb.jieba)) "
        "WITH (key_field='id')"
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {BM25_INDEX}")
    # 不 DROP EXTENSION pg_search：preload 库不可在事务里随意卸载，且其他对象可能依赖。
