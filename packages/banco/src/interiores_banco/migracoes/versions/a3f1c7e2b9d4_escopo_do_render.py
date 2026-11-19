"""escopo do render (cômodo ou pavimento inteiro)

Revisão: a3f1c7e2b9d4
Anterior: d96324d0a4c6
Criada em: 2026-11-19 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3f1c7e2b9d4"
down_revision: str | None = "d96324d0a4c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "render",
        sa.Column(
            "escopo",
            sa.String(length=10),
            server_default="comodo",
            nullable=False,
            comment="comodo | pavimento (aí ``comodo`` guarda o id do pavimento)",
        ),
    )
    op.alter_column(
        "render",
        "comodo",
        existing_type=sa.String(length=64),
        comment="id do cômodo ou do pavimento",
        existing_nullable=False,
    )


def downgrade() -> None:
    op.execute("DELETE FROM render WHERE escopo = 'pavimento'")
    op.alter_column(
        "render",
        "comodo",
        existing_type=sa.String(length=64),
        comment=None,
        existing_comment="id do cômodo ou do pavimento",
        existing_nullable=False,
    )
    op.drop_column("render", "escopo")
