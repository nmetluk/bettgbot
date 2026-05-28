"""Fix alembic_version column type to support longer revision IDs.

Revision ID: 0003b_fix_alembic_version_type
Revises: 0003_relax_event_archive
Create Date: 2026-05-28

This is a hotfix migration to expand version_num column from varchar(32)
to varchar(64) to support longer revision IDs like 0004_reminder_dispatch_log_indexes.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003b_fix_alembic_version_type"
down_revision: str | Sequence[str] | None = "0003_relax_event_archive"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE varchar(64)")


def downgrade() -> None:
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE varchar(32)")
