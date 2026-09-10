"""vybe_privacy_audit

Revision ID: 8a2b3c4d5e6f
Revises: 7f1a2b3c4d5e

Adds explicit person-to-application consent and append-only audit history for
Vybe-owned platform access controls.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "8a2b3c4d5e6f"
down_revision: Union[str, None] = "7f1a2b3c4d5e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vybe_consent_grants",
        sa.Column("consent_id", sa.UUID(), nullable=False),
        sa.Column("person_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("purpose", sa.String(length=512), nullable=False),
        sa.Column("scopes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("consent_id", name="pk_vybe_consent_grants"),
    )
    op.create_index(
        "ix_vybe_consent_person_application",
        "vybe_consent_grants",
        ["person_id", "application_id"],
        unique=False,
    )

    op.create_table(
        "vybe_audit_events",
        sa.Column("audit_id", sa.UUID(), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=True),
        sa.Column("person_id", sa.UUID(), nullable=True),
        sa.Column("actor_id", sa.String(length=255), nullable=True),
        sa.Column("resource_type", sa.String(length=128), nullable=True),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("request_id", sa.String(length=255), nullable=True),
        sa.Column("ip_address", sa.String(length=128), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.PrimaryKeyConstraint("audit_id", name="pk_vybe_audit_events"),
    )
    op.create_index(
        "ix_vybe_audit_person_occurred",
        "vybe_audit_events",
        ["person_id", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_vybe_audit_application_occurred",
        "vybe_audit_events",
        ["application_id", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_vybe_audit_application_occurred", table_name="vybe_audit_events")
    op.drop_index("ix_vybe_audit_person_occurred", table_name="vybe_audit_events")
    op.drop_table("vybe_audit_events")

    op.drop_index("ix_vybe_consent_person_application", table_name="vybe_consent_grants")
    op.drop_table("vybe_consent_grants")
