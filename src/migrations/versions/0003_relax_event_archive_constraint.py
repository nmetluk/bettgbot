"""relax event archive invariant: allow archived without result.

Revision ID: 0003_relax_event_archive
Revises: 0002_reminder_dispatch_log
Create Date: 2026-05-24

Расширяет CHECK `ck_event_result_archive_consistency` до трёх валидных
комбинаций — добавляет «архивный без result_outcome_id» для страховочного
пути архивации из TASK-018 (`EventService.archive_stale_events`).

См. также `docs/03-data-model.md` раздел Event «История инварианта».
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003_relax_event_archive"
down_revision: str | Sequence[str] | None = "0002_reminder_dispatch_log"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_OLD_CHECK = (
    "(result_outcome_id IS NULL AND is_archived = false) OR "
    "(result_outcome_id IS NOT NULL AND is_archived = true "
    "AND archived_at IS NOT NULL)"
)

_NEW_CHECK = (
    "(result_outcome_id IS NULL AND is_archived = false AND archived_at IS NULL) "
    "OR (result_outcome_id IS NULL AND is_archived = true AND archived_at IS NOT NULL) "
    "OR (result_outcome_id IS NOT NULL AND is_archived = true AND archived_at IS NOT NULL)"
)


def upgrade() -> None:
    op.drop_constraint("ck_event_result_archive_consistency", "event", type_="check")
    op.create_check_constraint("ck_event_result_archive_consistency", "event", _NEW_CHECK)


def downgrade() -> None:
    """Возвращает старый строгий CHECK.

    ВНИМАНИЕ: упадёт, если в БД есть события «архивные без итога»
    (т.е. строки, для которых страховочный путь архивации уже сработал).
    В таком случае оператор должен сначала вручную решить, что делать
    с такими событиями: либо вручную проставить result_outcome_id, либо
    раз-архивировать, либо удалить — в зависимости от бизнес-намерения.
    Downgrade намеренно не пытается auto-fix данные.
    """
    op.drop_constraint("ck_event_result_archive_consistency", "event", type_="check")
    op.create_check_constraint("ck_event_result_archive_consistency", "event", _OLD_CHECK)
