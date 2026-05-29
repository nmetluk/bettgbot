"""Add broadcast tables for user segment messaging.

Revision ID: 0005_broadcasts
Revises: 0004_reminder_dispatch_log_indexes
Create Date: 2026-05-29

Related to TASK-061.

- `broadcast` — рассылки по сегменту (all/active/category)
- `broadcast_delivery` — лог доставки (UNIQUE на broadcast_id + user_id для идемпотентности)

Mirror pattern of reminder_dispatch_log (TASK-017).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_broadcasts"
down_revision: str | Sequence[str] | None = "0004_reminder_dispatch_log_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Таблица broadcast
    op.create_table(
        "broadcast",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("segment", sa.String(length=10), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=10),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column("created_by_admin_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "total_recipients",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "sent_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "failed_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("broadcast_pkey")),
    )

    # FK: category_id
    op.create_foreign_key(
        "fk_broadcast_category_id",
        "broadcast",
        "category",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # FK: created_by_admin_id
    op.create_foreign_key(
        "fk_broadcast_created_by",
        "broadcast",
        "admin_user",
        ["created_by_admin_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # CHECK: category_id обязателен при segment='category'
    op.execute(
        """
        ALTER TABLE broadcast
        ADD CONSTRAINT ck_broadcast_category_required
        CHECK (
            (segment = 'category' AND category_id IS NOT NULL)
            OR (segment != 'category')
        )
        """
    )

    # Индексы
    op.create_index(
        "ix_broadcast_status_created",
        "broadcast",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_broadcast_created_by",
        "broadcast",
        ["created_by_admin_id"],
    )

    # Таблица broadcast_delivery (для идемпотентности)
    op.create_table(
        "broadcast_delivery",
        sa.Column("broadcast_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "delivered_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("broadcast_id", "user_id", name=op.f("broadcast_delivery_pkey")),
    )

    # Индекс для быстрой проверки "отправлено ли уже"
    op.create_index(
        "uq_broadcast_delivery",
        "broadcast_delivery",
        ["broadcast_id", "user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_broadcast_delivery", "broadcast_delivery")
    op.drop_table("broadcast_delivery")

    op.drop_index("ix_broadcast_created_by", "broadcast")
    op.drop_index("ix_broadcast_status_created", "broadcast")
    op.execute("ALTER TABLE broadcast DROP CONSTRAINT ck_broadcast_category_required")
    op.drop_constraint("fk_broadcast_created_by", "broadcast", type_="foreignkey")
    op.drop_constraint("fk_broadcast_category_id", "broadcast", type_="foreignkey")
    op.drop_table("broadcast")
