"""reminder_dispatch_log — таблица дедупликации отправленных напоминаний.

Revision ID: 0002_reminder_dispatch_log
Revises: 0001_init
Create Date: 2026-05-24

Связана с TASK-017. Уникальный constraint на (user_id, event_id, offset_minutes)
защищает от двойной отправки одного и того же напоминания.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_reminder_dispatch_log"
down_revision: str | Sequence[str] | None = "0001_init"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reminder_dispatch_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.Column("offset_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "dispatched_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["event.id"],
            name="fk_reminder_dispatch_log_event_id_event",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name="fk_reminder_dispatch_log_user_id_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_reminder_dispatch_log")),
        sa.UniqueConstraint(
            "user_id",
            "event_id",
            "offset_minutes",
            name="uq_reminder_dispatch_log_user_event_offset",
        ),
    )


def downgrade() -> None:
    op.drop_table("reminder_dispatch_log")
