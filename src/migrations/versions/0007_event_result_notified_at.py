"""Add result_notified_at to Event for idempotent admin result notifications.

Revision ID: 0007_event_result_notified_at
Revises: 0006_broadcast_category_restrict
Create Date: 2026-06-01

Related to TASK-097.

- `event.result_notified_at` (nullable) — метка, что бот уже разослал пост-итоговую
  сводку (с CSV угадавших) во все ADMIN_TELEGRAM_CHAT_IDS.
- Используется джобом `dispatch_event_result_notifications` (FOR UPDATE SKIP LOCKED,
  идемпотентно, commit после каждой отправки).
- НЕ добавляется в CHECK-инвариант ck_event_result_archive_consistency.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_event_result_notified_at"
down_revision: str | Sequence[str] | None = "0006_broadcast_category_restrict"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "event",
        sa.Column(
            "result_notified_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("event", "result_notified_at")
