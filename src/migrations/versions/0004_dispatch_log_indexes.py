"""Add indexes on reminder_dispatch_log for retention and cascade performance.

Revision ID: 0004_dispatch_log_indexes
Revises: 0003_relax_event_archive
Create Date: 2026-05-27

Related to TASK-048.

- Index on `dispatched_at` for efficient cleanup (DELETE WHERE dispatched_at < cutoff).
- Indexes on `user_id` and `event_id` for FK cascade and selective queries.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0004_dispatch_log_indexes"
down_revision: str | Sequence[str] | None = "0003_relax_event_archive"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_reminder_dispatch_log_user_id",
        "reminder_dispatch_log",
        ["user_id"],
    )
    op.create_index(
        "ix_reminder_dispatch_log_event_id",
        "reminder_dispatch_log",
        ["event_id"],
    )
    op.create_index(
        "ix_reminder_dispatch_log_dispatched_at",
        "reminder_dispatch_log",
        ["dispatched_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_reminder_dispatch_log_dispatched_at", "reminder_dispatch_log")
    op.drop_index("ix_reminder_dispatch_log_event_id", "reminder_dispatch_log")
    op.drop_index("ix_reminder_dispatch_log_user_id", "reminder_dispatch_log")
