"""create users table and add operator_id to engagements

Revision ID: 0004_users_and_operators
Revises: 0003_evidence
Create Date: 2026-07-31

"""

from alembic import op
import sqlalchemy as sa


revision = "0004_users_and_operators"
down_revision = "0003_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="OPERATOR"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)

    with op.batch_alter_table("engagements", schema=None) as batch_op:
        batch_op.add_column(sa.Column("operator_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_engagements_operator_id"), ["operator_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_engagements_users_operator_id", "users", ["operator_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("engagements", schema=None) as batch_op:
        batch_op.drop_constraint("fk_engagements_users_operator_id", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_engagements_operator_id"))
        batch_op.drop_column("operator_id")

    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_table("users")
