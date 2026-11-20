"""tipos de porta e janela: estilo, modelo, abertura e folhas

Revisão: c4e8a2d6f1b3
Anterior: b7e4d2a1c3f5
Criada em: 2026-11-20 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c4e8a2d6f1b3"
down_revision: str | None = "b7e4d2a1c3f5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "abertura",
        sa.Column(
            "estilo",
            sa.String(length=20),
            nullable=True,
            comment="porta: lisa | almofadada | vidro | veneziana",
        ),
    )
    op.add_column(
        "abertura",
        sa.Column(
            "abertura",
            sa.String(length=20),
            nullable=True,
            comment="janela: correr | basculante | maxim_ar | abrir | fixa",
        ),
    )
    op.add_column(
        "abertura",
        sa.Column("folhas", sa.Integer(), nullable=True, comment="janela: número de folhas"),
    )
    op.add_column(
        "abertura",
        sa.Column("modelo", sa.String(length=64), nullable=True, comment="modelo do catálogo"),
    )


def downgrade() -> None:
    for coluna in ("modelo", "folhas", "abertura", "estilo"):
        op.drop_column("abertura", coluna)
