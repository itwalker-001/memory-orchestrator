"""projects uuid pk + memories fk

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

GLOBAL_ID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    # 1. 给 projects 加 slug 列（copy from id），加 new_id UUID 列
    op.add_column("projects", sa.Column("slug", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("new_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute("UPDATE projects SET slug = id, new_id = gen_random_uuid()")
    op.alter_column("projects", "slug", nullable=False)

    # 2. 插入 global sentinel project
    op.execute(
        f"INSERT INTO projects (id, slug, new_id, display_name, root_paths, first_seen_at, last_active_at) "
        f"VALUES ('*', '*', '{GLOBAL_ID}', 'Global', '{{}}', now(), now()) "
        f"ON CONFLICT (id) DO NOTHING"
    )

    # 3. memories: 加 project_uuid 列，从 projects 映射
    op.add_column("memories", sa.Column("project_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(
        "UPDATE memories m SET project_uuid = "
        "COALESCE((SELECT new_id FROM projects p WHERE p.id = m.project_id), "
        f"'{GLOBAL_ID}')"
    )
    # sessions: 加 project_uuid 列
    op.add_column("sessions", sa.Column("project_uuid", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(
        "UPDATE sessions s SET project_uuid = "
        "COALESCE((SELECT new_id FROM projects p WHERE p.id = s.project_id), "
        f"'{GLOBAL_ID}')"
    )

    # 4. projects: 重建 PK（new_id → id）
    op.drop_constraint("projects_pkey", "projects", type_="primary")
    op.execute("ALTER TABLE projects DROP COLUMN id")
    op.execute(f"ALTER TABLE projects RENAME COLUMN new_id TO id")
    op.create_primary_key("projects_pkey", "projects", ["id"])
    op.create_unique_constraint("projects_slug_key", "projects", ["slug"])

    # 5. memories: 删旧 project_id，project_uuid 改名并加 FK
    op.drop_index("memories_project_type_idx", table_name="memories")
    op.execute("ALTER TABLE memories DROP COLUMN project_id")
    op.execute("ALTER TABLE memories RENAME COLUMN project_uuid TO project_id")
    op.alter_column("memories", "project_id", nullable=False)
    op.create_foreign_key("memories_project_id_fkey", "memories", "projects", ["project_id"], ["id"])
    op.create_index(
        "memories_project_type_idx", "memories", ["project_id", "type"],
        postgresql_where=sa.text("superseded_by IS NULL"),
    )

    # 6. sessions: 删旧 project_id，project_uuid 改名并加 FK
    op.execute("ALTER TABLE sessions DROP COLUMN project_id")
    op.execute("ALTER TABLE sessions RENAME COLUMN project_uuid TO project_id")
    op.alter_column("sessions", "project_id", nullable=False)
    op.create_foreign_key("sessions_project_id_fkey", "sessions", "projects", ["project_id"], ["id"])


def downgrade() -> None:
    raise NotImplementedError("downgrade not supported for this migration")
