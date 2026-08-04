"""add error_message to cracking_jobs

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-04

Almacena el motivo real cuando hashcat termina con error, para no confundirlo
con un keyspace agotado (EXHAUSTED).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("cracking_jobs", sa.Column("error_message", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("cracking_jobs", "error_message")
