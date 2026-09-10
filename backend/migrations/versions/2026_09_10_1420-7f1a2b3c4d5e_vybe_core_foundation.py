"""vybe_core_foundation

Revision ID: 7f1a2b3c4d5e
Revises: cf76dead11f5

Creates the durable infrastructure owned by ``vybe_core``. These tables are
kept separate from the inherited Open Wearables data model so the new platform
can be migrated incrementally without coupling the immutable evidence pipeline
to legacy event/timeseries tables.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "7f1a2b3c4d5e"
down_revision: Union[str, None] = "cf76dead11f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vybe_evidence",
        sa.Column("evidence_id", sa.UUID(), nullable=False),
        sa.Column("person_id", sa.UUID(), nullable=False),
        sa.Column("metric", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("device_id", sa.String(length=255), nullable=True),
        sa.Column("sensor", sa.String(length=128), nullable=True),
        sa.Column("source_record_id", sa.String(length=255), nullable=True),
        sa.Column("firmware_version", sa.String(length=128), nullable=True),
        sa.Column("signal_quality", sa.Float(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("completeness", sa.Float(), nullable=True),
        sa.Column("quality_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processor", sa.String(length=128), nullable=False),
        sa.Column("processing_version", sa.String(length=128), nullable=False),
        sa.Column("raw_sha256", sa.String(length=64), nullable=True),
        sa.Column("parent_evidence_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("evidence_id", name="pk_vybe_evidence"),
    )
    op.create_index(
        "ix_vybe_evidence_person_recorded",
        "vybe_evidence",
        ["person_id", "recorded_at"],
        unique=False,
    )
    op.create_index(
        "ix_vybe_evidence_person_metric_recorded",
        "vybe_evidence",
        ["person_id", "metric", "recorded_at"],
        unique=False,
    )
    op.create_index(
        "ix_vybe_evidence_source_record",
        "vybe_evidence",
        ["provider", "source_record_id"],
        unique=False,
    )

    op.create_table(
        "vybe_sync_checkpoints",
        sa.Column("person_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("stream", sa.String(length=128), nullable=False),
        sa.Column("cursor", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("person_id", "provider", "stream", name="pk_vybe_sync_checkpoints"),
    )

    op.create_table(
        "vybe_idempotency_keys",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key", name="pk_vybe_idempotency_keys"),
    )

    op.create_table(
        "vybe_provider_connections",
        sa.Column("connection_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("person_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("external_user_id", sa.String(length=255), nullable=True),
        sa.Column("token_reference", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("connection_id", name="pk_vybe_provider_connections"),
        sa.UniqueConstraint(
            "application_id",
            "person_id",
            "provider",
            name="uq_vybe_connection_application_person_provider",
        ),
    )
    op.create_index(
        "ix_vybe_provider_connections_person",
        "vybe_provider_connections",
        ["application_id", "person_id"],
        unique=False,
    )

    op.create_table(
        "vybe_oauth_authorization_states",
        sa.Column("state_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("person_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("redirect_uri", sa.String(length=2048), nullable=False),
        sa.Column("scopes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("state_digest", sa.String(length=64), nullable=False),
        sa.Column("verifier_reference", sa.String(length=512), nullable=False),
        sa.Column("code_challenge", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("state_id", name="pk_vybe_oauth_authorization_states"),
    )
    op.create_index(
        "ix_vybe_oauth_state_expiry",
        "vybe_oauth_authorization_states",
        ["expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_vybe_oauth_state_expiry", table_name="vybe_oauth_authorization_states")
    op.drop_table("vybe_oauth_authorization_states")

    op.drop_index("ix_vybe_provider_connections_person", table_name="vybe_provider_connections")
    op.drop_table("vybe_provider_connections")

    op.drop_table("vybe_idempotency_keys")
    op.drop_table("vybe_sync_checkpoints")

    op.drop_index("ix_vybe_evidence_source_record", table_name="vybe_evidence")
    op.drop_index("ix_vybe_evidence_person_metric_recorded", table_name="vybe_evidence")
    op.drop_index("ix_vybe_evidence_person_recorded", table_name="vybe_evidence")
    op.drop_table("vybe_evidence")
