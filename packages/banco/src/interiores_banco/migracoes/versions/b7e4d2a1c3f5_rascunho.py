"""rascunho: passos ainda não salvos

Revisão: b7e4d2a1c3f5
Anterior: a3f1c7e2b9d4
Criada em: 2026-11-19 21:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e4d2a1c3f5"
down_revision: str | None = "a3f1c7e2b9d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projeto",
        sa.Column(
            "rascunho_desde",
            sa.Integer(),
            nullable=True,
            comment="versão salva onde o rascunho começou (None: sem rascunho); "
            "as versões acima dela são passos ainda não salvos",
        ),
    )


def downgrade() -> None:
    op.drop_column("projeto", "rascunho_desde")
