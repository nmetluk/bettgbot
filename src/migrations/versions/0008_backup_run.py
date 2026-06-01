"""Add backup_run table (TASK-099: backup health heartbeat).

Revision ID: 0008_backup_run
Revises: 0007_event_result_notified_at
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0008_backup_run"
down_revision = "0007_event_result_notified_at"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "backup_run",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("started_at", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("finished_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=True),
        sa.Column("host", sa.String(length=255), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_backup_run"),
    )
    op.create_index(
        "ix_backup_run_finished_at",
        "backup_run",
        [sa.text("finished_at DESC")],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_backup_run_finished_at", table_name="backup_run")
    op.drop_table("backup_run")
