"""init — все 8 таблиц по docs/03-data-model.md.

Revision ID: 0001_init
Revises:
Create Date: 2026-05-23

Содержит начальную схему БД:
- admin_user, category, user, audit_log, event, reminder_setting, outcome, prediction
- все индексы из docs/03-data-model.md, включая partial `ix_event_predictions_close_at_active`
- CHECK constraints на event: ck_event_close_before_start, ck_event_result_archive_consistency
- циклическая FK event ↔ outcome через use_alter (в `create_table` для event, downgrade
  явно дропает её до drop_table outcome)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_init"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_user",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("login", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=128), nullable=False),
        sa.Column("full_name", sa.String(length=128), nullable=True),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_login_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_user")),
        sa.UniqueConstraint("login", name="uq_admin_user_login"),
    )
    op.create_table(
        "category",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("slug", sa.String(length=64), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_category")),
        sa.UniqueConstraint("name", name="uq_category_name"),
        sa.UniqueConstraint("slug", name="uq_category_slug"),
    )
    op.create_index(
        "ix_category_is_active_sort_order",
        "category",
        ["is_active", "sort_order"],
        unique=False,
    )
    op.create_table(
        "user",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tg_user_id", sa.BigInteger(), nullable=False),
        sa.Column("phone", sa.String(length=20), nullable=False),
        sa.Column("tg_username", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=64), nullable=False),
        sa.Column("last_name", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "last_seen_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "is_blocked",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user")),
        sa.UniqueConstraint("phone", name="uq_user_phone"),
        sa.UniqueConstraint("tg_user_id", name="uq_user_tg_user_id"),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("admin_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["admin_id"],
            ["admin_user.id"],
            name="fk_audit_log_admin_id_admin_user",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_log")),
    )
    op.create_index(
        "ix_audit_log_admin_id_created_at",
        "audit_log",
        ["admin_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_audit_log_created_at",
        "audit_log",
        [sa.literal_column("created_at DESC")],
        unique=False,
    )
    # `event` создаётся без FK на outcome (use_alter), он добавляется ALTER'ом
    # после создания таблицы outcome — см. конец upgrade().
    op.create_table(
        "event",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("starts_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("predictions_close_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("result_outcome_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "is_published",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("archived_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_admin_id", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "predictions_close_at <= starts_at",
            name="ck_event_close_before_start",
        ),
        sa.CheckConstraint(
            "(result_outcome_id IS NULL AND is_archived = false) OR "
            "(result_outcome_id IS NOT NULL AND is_archived = true "
            "AND archived_at IS NOT NULL)",
            name="ck_event_result_archive_consistency",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["category.id"],
            name="fk_event_category_id_category",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_admin_id"],
            ["admin_user.id"],
            name="fk_event_created_by_admin_id_admin_user",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_event")),
    )
    op.create_index(
        "ix_event_category_id_starts_at",
        "event",
        ["category_id", "starts_at"],
        unique=False,
    )
    op.create_index(
        "ix_event_is_published_is_archived_starts_at",
        "event",
        ["is_published", "is_archived", "starts_at"],
        unique=False,
    )
    op.create_index(
        "ix_event_predictions_close_at_active",
        "event",
        ["predictions_close_at"],
        unique=False,
        postgresql_where=sa.text("NOT is_archived"),
    )
    op.create_table(
        "reminder_setting",
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "offsets_minutes",
            postgresql.ARRAY(sa.Integer()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name="fk_reminder_setting_user_id_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_reminder_setting")),
    )
    op.create_table(
        "outcome",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.Column("label", sa.String(length=128), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["event.id"],
            name="fk_outcome_event_id_event",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_outcome")),
    )
    op.create_index(
        "ix_outcome_event_id_sort_order",
        "outcome",
        ["event_id", "sort_order"],
        unique=False,
    )
    op.create_table(
        "prediction",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.Column("outcome_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(
            ["event_id"],
            ["event.id"],
            name="fk_prediction_event_id_event",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["outcome_id"],
            ["outcome.id"],
            name="fk_prediction_outcome_id_outcome",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
            name="fk_prediction_user_id_user",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_prediction")),
        sa.UniqueConstraint("user_id", "event_id", name="uq_prediction_user_event"),
    )
    op.create_index("ix_prediction_event_id", "prediction", ["event_id"], unique=False)
    op.create_index(
        "ix_prediction_user_id_created_at",
        "prediction",
        ["user_id", sa.literal_column("created_at DESC")],
        unique=False,
    )
    # Циклическая FK event.result_outcome_id → outcome.id — добавляется ALTER'ом
    # после создания обеих таблиц (use_alter=True в модели).
    op.create_foreign_key(
        "fk_event_result_outcome_id",
        "event",
        "outcome",
        ["result_outcome_id"],
        ["id"],
        ondelete="RESTRICT",
        use_alter=True,
    )


def downgrade() -> None:
    # Сначала дропаем циклическую FK, чтобы можно было удалить outcome раньше event.
    op.drop_constraint(
        "fk_event_result_outcome_id",
        "event",
        type_="foreignkey",
    )
    op.drop_index("ix_prediction_user_id_created_at", table_name="prediction")
    op.drop_index("ix_prediction_event_id", table_name="prediction")
    op.drop_table("prediction")
    op.drop_index("ix_outcome_event_id_sort_order", table_name="outcome")
    op.drop_table("outcome")
    op.drop_table("reminder_setting")
    op.drop_index(
        "ix_event_predictions_close_at_active",
        table_name="event",
        postgresql_where=sa.text("NOT is_archived"),
    )
    op.drop_index("ix_event_is_published_is_archived_starts_at", table_name="event")
    op.drop_index("ix_event_category_id_starts_at", table_name="event")
    op.drop_table("event")
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_index("ix_audit_log_admin_id_created_at", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_table("user")
    op.drop_index("ix_category_is_active_sort_order", table_name="category")
    op.drop_table("category")
    op.drop_table("admin_user")
