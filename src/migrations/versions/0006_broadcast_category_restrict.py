"""Change broadcast.category_id FK from SET NULL to RESTRICT.

Revision ID: 0006_broadcast_category_restrict
Revises: 0005_broadcasts
Create Date: 2026-05-31

Related to TASK-085 (M1 from 2026-05-31-full-audit).

- FK `fk_broadcast_category_id` now ondelete="RESTRICT" (consistent with event.category_id).
- CHECK `ck_broadcast_category_required` unchanged (segment='category' ⇒ category_id NOT NULL).
- Category delete now guarded by CategoryHasBroadcastsError (in addition to HasEventsError).

This prevents silent loss of historical segment attribution for past broadcasts
and gives admin a clear domain error instead of opaque Postgres CHECK violation.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0006_broadcast_category_restrict"
down_revision: str | Sequence[str] | None = "0005_broadcasts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Меняем ondelete с SET NULL на RESTRICT.
    # Сначала дропаем старый FK, потом создаём новый с тем же именем.
    op.drop_constraint("fk_broadcast_category_id", "broadcast", type_="foreignkey")

    op.create_foreign_key(
        "fk_broadcast_category_id",
        "broadcast",
        "category",
        ["category_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    # Возврат к SET NULL (для отката миграции).
    op.drop_constraint("fk_broadcast_category_id", "broadcast", type_="foreignkey")

    op.create_foreign_key(
        "fk_broadcast_category_id",
        "broadcast",
        "category",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )
