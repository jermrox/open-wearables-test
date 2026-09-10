"""vybe_auth_identity

Revision ID: 9b3c4d5e6f70
Revises: 8a2b3c4d5e6f

Adds Vybe-owned organization, application, and hashed API credential identity.
Plaintext API secrets are never persisted.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "9b3c4d5e6f70"
down_revision: Union[str, None] = "8a2b3c4d5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vybe_organizations",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("organization_id", name="pk_vybe_organizations"),
    )

    op.create_table(
        "vybe_applications",
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["vybe_organizations.organization_id"],
            name="fk_vybe_applications_organization_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("application_id", name="pk_vybe_applications"),
        sa.UniqueConstraint("organization_id", "name", name="uq_vybe_application_organization_name"),
    )

    op.create_table(
        "vybe_api_credentials",
        sa.Column("credential_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        sa.Column("key_prefix", sa.String(length=128), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("scopes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["vybe_applications.application_id"],
            name="fk_vybe_api_credentials_application_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("credential_id", name="pk_vybe_api_credentials"),
        sa.UniqueConstraint("key_prefix", name="uq_vybe_api_credentials_key_prefix"),
    )
    op.create_index(
        "ix_vybe_api_credentials_application",
        "vybe_api_credentials",
        ["application_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_vybe_api_credentials_application", table_name="vybe_api_credentials")
    op.drop_table("vybe_api_credentials")
    op.drop_table("vybe_applications")
    op.drop_table("vybe_organizations")
