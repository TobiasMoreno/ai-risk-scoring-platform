"""batch_jobs and idempotency columns

Revision ID: a1b2c3d4e5f6
Revises: 2d5de54b4b10
Create Date: 2026-05-21 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "2d5de54b4b10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "batch_jobs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("total_records", sa.Integer(), nullable=False),
        sa.Column("processed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed", sa.Integer(), server_default="0", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_index("ix_batch_jobs_status", "batch_jobs", ["status"], unique=False)
    op.create_index("ix_batch_jobs_created_at", "batch_jobs", ["created_at"], unique=False)

    op.add_column(
        "prediction_requests",
        sa.Column("job_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "prediction_requests",
        sa.Column("external_id", sa.String(), nullable=True),
    )
    op.create_index(
        "ix_prediction_requests_job_id",
        "prediction_requests",
        ["job_id"],
        unique=False,
    )
    op.create_index(
        "uq_prediction_requests_job_external",
        "prediction_requests",
        ["job_id", "external_id"],
        unique=True,
        postgresql_where=sa.text("job_id IS NOT NULL AND external_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_prediction_requests_job_external", table_name="prediction_requests"
    )
    op.drop_index("ix_prediction_requests_job_id", table_name="prediction_requests")
    op.drop_column("prediction_requests", "external_id")
    op.drop_column("prediction_requests", "job_id")

    op.drop_index("ix_batch_jobs_created_at", table_name="batch_jobs")
    op.drop_index("ix_batch_jobs_status", table_name="batch_jobs")
    op.drop_table("batch_jobs")
