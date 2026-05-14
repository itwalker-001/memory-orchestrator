"""backfill builtin skeleton node tags

Revision ID: 0013_backfill_builtin_tags
Revises: 0012_skeleton_node_tags
Create Date: 2026-05-14
"""
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


def _pg_array(tags: list[str]) -> str:
    escaped = ", ".join(f"'{t}'" for t in tags)
    return f"ARRAY[{escaped}]::text[]"


def upgrade() -> None:
    for name, tags in _BUILTIN_TAGS:
        op.execute(
            f"""
            UPDATE project_skeleton_nodes
            SET    tags = {_pg_array(tags)}
            WHERE  name = '{name}'
              AND  tags = '{{}}'
            """
        )


def downgrade() -> None:
    for name, _ in _BUILTIN_TAGS:
        op.execute(
            f"""
            UPDATE project_skeleton_nodes
            SET    tags = '{{}}'
            WHERE  name = '{name}'
            """
        )
