"""acordes dos picos

Revision ID: a3c51e7b2d90
Revises: 9d5f200917d2
Create Date: 2026-11-12 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3c51e7b2d90"
down_revision: str | Sequence[str] | None = "9d5f200917d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "analyses",
        sa.Column("top_chords", sa.JSON(), server_default="[]", nullable=False),
        schema="tonalidade",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("analyses", "top_chords", schema="tonalidade")
