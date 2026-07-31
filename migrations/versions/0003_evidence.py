"""evidence: extend Capture with job_id, category, metadata

Revision ID: 0003
Revises: fa985ea3e160
Create Date: 2026-07-29

Extiende la tabla ``captures`` con columnas para asociar evidencia a trabajos
y almacenar metadatos adicionales (minuta §28, §30).
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, Sequence[str], None] = "fa985ea3e160"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("captures", schema=None) as batch_op:
        batch_op.add_column(sa.Column("job_id", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("category", sa.String(32), server_default="original", nullable=False)
        )
        batch_op.add_column(sa.Column("original_filename", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("bssid", sa.String(17), nullable=True))
        batch_op.add_column(sa.Column("ssid", sa.String(64), nullable=True))
        batch_op.add_column(
            sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'"))
        )
        batch_op.add_column(sa.Column("derived_from_id", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("size_bytes", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_captures_job_id", "jobs", ["job_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_foreign_key(
            "fk_captures_derived", "captures", ["derived_from_id"], ["id"], ondelete="SET NULL"
        )
        batch_op.create_index("ix_captures_job_id", ["job_id"])
        batch_op.create_index("ix_captures_category", ["category"])

    op.create_index(
        "ix_captures_engagement_job", "captures", ["engagement_id", "job_id"]
    )
    op.create_index(
        "ix_captures_job_category", "captures", ["job_id", "category"]
    )


def downgrade() -> None:
    op.drop_index("ix_captures_job_category", table_name="captures")
    op.drop_index("ix_captures_engagement_job", table_name="captures")
    with op.batch_alter_table("captures", schema=None) as batch_op:
        batch_op.drop_index("ix_captures_category")
        batch_op.drop_index("ix_captures_job_id")
        batch_op.drop_constraint("fk_captures_derived", type_="foreignkey")
        batch_op.drop_constraint("fk_captures_job_id", type_="foreignkey")
        batch_op.drop_column("size_bytes")
        batch_op.drop_column("derived_from_id")
        batch_op.drop_column("metadata")
        batch_op.drop_column("ssid")
        batch_op.drop_column("bssid")
        batch_op.drop_column("original_filename")
        batch_op.drop_column("category")
        batch_op.drop_column("job_id")