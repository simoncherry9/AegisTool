"""initial schema — entidades de la minuta §28

Revision ID: 0001
Revises:
Create Date: 2026-07-29

Crea el esquema inicial: engagements, scope_targets, access_points, stations,
captures, handshake_artifacts, cracking_jobs y findings.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "engagements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("client", sa.String(length=255), nullable=False),
        sa.Column("operator", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("authorization_reference", sa.String(length=255), nullable=True),
        sa.Column("permissions", sa.JSON(), nullable=False),
        sa.Column("limits", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_engagements_status", "engagements", ["status"])

    op.create_table(
        "scope_targets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("engagement_id", sa.Integer(), nullable=False),
        sa.Column("ssid", sa.String(length=64), nullable=True),
        sa.Column("bssid", sa.String(length=17), nullable=True),
        sa.Column("channel", sa.Integer(), nullable=True),
        sa.Column("band", sa.String(length=8), nullable=True),
        sa.Column("permission_level", sa.String(length=32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scope_targets_engagement_id", "scope_targets", ["engagement_id"])
    op.create_index("ix_scope_targets_bssid", "scope_targets", ["bssid"])

    op.create_table(
        "access_points",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("engagement_id", sa.Integer(), nullable=False),
        sa.Column("ssid", sa.String(length=64), nullable=True),
        sa.Column("bssid", sa.String(length=17), nullable=False),
        sa.Column("vendor", sa.String(length=128), nullable=True),
        sa.Column("channel", sa.Integer(), nullable=True),
        sa.Column("frequency", sa.Integer(), nullable=True),
        sa.Column("signal", sa.Integer(), nullable=True),
        sa.Column("protocol", sa.String(length=16), nullable=True),
        sa.Column("akm", sa.String(length=64), nullable=True),
        sa.Column("cipher", sa.String(length=32), nullable=True),
        sa.Column("pmf", sa.String(length=16), nullable=True),
        sa.Column("wps", sa.Boolean(), nullable=False),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_access_points_engagement_id", "access_points", ["engagement_id"])
    op.create_index("ix_access_points_bssid", "access_points", ["bssid"])

    op.create_table(
        "stations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("mac", sa.String(length=17), nullable=False),
        sa.Column("randomized", sa.Boolean(), nullable=False),
        sa.Column("vendor", sa.String(length=128), nullable=True),
        sa.Column("associated_bssid", sa.String(length=17), nullable=True),
        sa.Column("signal", sa.Integer(), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("controlled", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stations_mac", "stations", ["mac"])
    op.create_index("ix_stations_associated_bssid", "stations", ["associated_bssid"])

    op.create_table(
        "captures",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("engagement_id", sa.Integer(), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("format", sa.String(length=16), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("interface", sa.String(length=32), nullable=True),
        sa.Column("channel", sa.Integer(), nullable=True),
        sa.Column("tool", sa.String(length=64), nullable=True),
        sa.Column("tool_version", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_captures_engagement_id", "captures", ["engagement_id"])

    op.create_table(
        "handshake_artifacts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("access_point_id", sa.Integer(), nullable=True),
        sa.Column("station_id", sa.Integer(), nullable=True),
        sa.Column("capture_id", sa.Integer(), nullable=True),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("message_pair", sa.String(length=16), nullable=True),
        sa.Column("quality", sa.String(length=32), nullable=False),
        sa.Column("validated", sa.Boolean(), nullable=False),
        sa.Column("hash22000_path", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["access_point_id"], ["access_points.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["station_id"], ["stations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["capture_id"], ["captures.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_handshake_artifacts_access_point_id", "handshake_artifacts", ["access_point_id"])
    op.create_index("ix_handshake_artifacts_station_id", "handshake_artifacts", ["station_id"])
    op.create_index("ix_handshake_artifacts_capture_id", "handshake_artifacts", ["capture_id"])

    op.create_table(
        "cracking_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("artifact_id", sa.Integer(), nullable=True),
        sa.Column("strategy", sa.String(length=32), nullable=False),
        sa.Column("keyspace", sa.Integer(), nullable=True),
        sa.Column("progress", sa.Float(), nullable=True),
        sa.Column("speed", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("recovered", sa.Boolean(), nullable=False),
        sa.Column("encrypted_secret", sa.Text(), nullable=True),
        sa.Column("restore_path", sa.String(length=512), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["artifact_id"], ["handshake_artifacts.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cracking_jobs_artifact_id", "cracking_jobs", ["artifact_id"])
    op.create_index("ix_cracking_jobs_status", "cracking_jobs", ["status"])

    op.create_table(
        "findings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("engagement_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("rule_id", sa.String(length=64), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("impact", sa.Text(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("remediation", sa.Text(), nullable=True),
        sa.Column("affected_assets", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["engagement_id"], ["engagements.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_findings_engagement_id", "findings", ["engagement_id"])
    op.create_index("ix_findings_severity", "findings", ["severity"])
    op.create_index("ix_findings_status", "findings", ["status"])

    # Índices compuestos (de models.py)
    op.create_index(
        "ix_scope_targets_engagement_ssid", "scope_targets", ["engagement_id", "ssid"]
    )
    op.create_index(
        "ix_access_points_engagement_bssid", "access_points", ["engagement_id", "bssid"]
    )


def downgrade() -> None:
    op.drop_index("ix_access_points_engagement_bssid", table_name="access_points")
    op.drop_index("ix_scope_targets_engagement_ssid", table_name="scope_targets")
    op.drop_index("ix_findings_status", table_name="findings")
    op.drop_index("ix_findings_severity", table_name="findings")
    op.drop_index("ix_findings_engagement_id", table_name="findings")
    op.drop_table("findings")
    op.drop_index("ix_cracking_jobs_status", table_name="cracking_jobs")
    op.drop_index("ix_cracking_jobs_artifact_id", table_name="cracking_jobs")
    op.drop_table("cracking_jobs")
    op.drop_index("ix_handshake_artifacts_capture_id", table_name="handshake_artifacts")
    op.drop_index("ix_handshake_artifacts_station_id", table_name="handshake_artifacts")
    op.drop_index("ix_handshake_artifacts_access_point_id", table_name="handshake_artifacts")
    op.drop_table("handshake_artifacts")
    op.drop_index("ix_captures_engagement_id", table_name="captures")
    op.drop_table("captures")
    op.drop_index("ix_stations_associated_bssid", table_name="stations")
    op.drop_index("ix_stations_mac", table_name="stations")
    op.drop_table("stations")
    op.drop_index("ix_access_points_bssid", table_name="access_points")
    op.drop_index("ix_access_points_engagement_id", table_name="access_points")
    op.drop_table("access_points")
    op.drop_index("ix_scope_targets_bssid", table_name="scope_targets")
    op.drop_index("ix_scope_targets_engagement_id", table_name="scope_targets")
    op.drop_table("scope_targets")
    op.drop_index("ix_engagements_status", table_name="engagements")
    op.drop_table("engagements")
