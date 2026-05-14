# -*- coding: utf-8 -*-
"""backfill builtin skeleton node tags

Revision ID: 0013_backfill_builtin_tags
Revises: 0012_skeleton_node_tags
Create Date: 2026-05-14
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from alembic import op

revision = "0013_backfill_builtin_tags"
down_revision = "0012_skeleton_node_tags"
branch_labels = None
depends_on = None

_BUILTIN_TAGS: list[tuple[str, list[str]]] = [
    ("项目概况",  ["overview", "architecture", "stack", "system"]),
    ("需求",      ["requirement", "user_story", "spec"]),
    ("设计",      ["design", "architecture", "api", "schema"]),
    ("技术栈",    ["stack", "tech", "dependency"]),
    ("前端",      ["frontend", "ui", "component", "reactive"]),
    ("后端",      ["backend", "api", "service", "logic"]),
    ("数据库",    ["database", "sql", "index", "transaction"]),
    ("测试",      ["testing", "qa", "mock", "e2e"]),
    ("部署",      ["deploy", "ci_cd", "devops", "infra"]),
    ("决策记录",  ["decision", "tradeoff", "architecture_choice"]),
    ("经验库",    ["experience", "best_practice", "pitfall", "debug"]),
]

_STMT_UP = sa.text(
    "UPDATE project_skeleton_nodes "
    "SET tags = :tags "
    "WHERE name = :name AND tags = '{}'"
).bindparams(
    sa.bindparam("tags", type_=ARRAY(sa.Text())),
    sa.bindparam("name", type_=sa.Text()),
)

_STMT_DOWN = sa.text(
    "UPDATE project_skeleton_nodes "
    "SET tags = '{}' "
    "WHERE name = :name"
).bindparams(
    sa.bindparam("name", type_=sa.Text()),
)


def upgrade() -> None:
    conn = op.get_bind()
    for name, tags in _BUILTIN_TAGS:
        conn.execute(_STMT_UP, {"name": name, "tags": tags})


def downgrade() -> None:
    conn = op.get_bind()
    for name, _ in _BUILTIN_TAGS:
        conn.execute(_STMT_DOWN, {"name": name})
