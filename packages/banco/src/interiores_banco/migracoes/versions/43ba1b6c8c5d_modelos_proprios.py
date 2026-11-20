"""modelos próprios: móveis editados guardados para reaproveitar

Revisão: 43ba1b6c8c5d
Anterior: c4e8a2d6f1b3
Criada em: 2026-11-20 05:43:40
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "43ba1b6c8c5d"
down_revision: str | None = "c4e8a2d6f1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "modelo_proprio",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("codigo", sa.String(length=64), nullable=False),
        sa.Column("nome", sa.String(length=120), nullable=False),
        sa.Column(
            "tipo",
            sa.String(length=40),
            nullable=False,
            comment="tipo do catálogo (cama, sob_medida...)",
        ),
        sa.Column(
            "dados",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            comment="o móvel sem id/centro/rotacao (interiores_core.modelos_proprios)",
        ),
        sa.Column(
            "criado_em",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_modelo_proprio")),
        sa.UniqueConstraint("codigo", name=op.f("uq_modelo_proprio_codigo")),
    )


def downgrade() -> None:
    op.drop_table("modelo_proprio")
