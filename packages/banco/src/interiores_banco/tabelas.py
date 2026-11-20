"""Tabelas do PostgreSQL: o modelo do core mapeado para consulta.

Organização:

- uma tabela por entidade (``pavimento``, ``parede``, ``abertura``, ``comodo``,
  ``instalacao``, ``estrutura``, ``movel``, ``variacao``) com colunas de verdade para
  o que se pesquisa (lados, tipos, coordenadas, referências por código);
- ``medida``: as medidas de todas as entidades numa tabela só (entidade, campo,
  valor em mm, origem, obs, data), para perguntas como "o que ainda é estimado?".
  As medidas internas de um planejado (chapas, vãos) ficam dentro de
  ``movel.extra`` (JSONB), junto com a construção;
- ``historico``: cada alteração (versão, caminho, antes → depois, fonte);
- ``snapshot``: o conteúdo inteiro de cada versão em JSONB (pesquisa livre e
  restauração).

As linhas das entidades representam a versão **atual**; a cada gravação elas são
substituídas numa transação e o passado fica em ``snapshot`` e ``historico``. O
código (``codigo``) é o ``id`` do JSON; ``id`` aqui é a chave do banco.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, ClassVar

from sqlalchemy import (
    ARRAY,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

CONVENCAO = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=CONVENCAO)
    type_annotation_map: ClassVar[dict[Any, Any]] = {dict[str, Any]: JSONB, list[Any]: JSONB}


Codigo = String(64)


class Projeto(Base):
    __tablename__ = "projeto"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    codigo: Mapped[str] = mapped_column(Codigo, unique=True)
    schema_version: Mapped[int]
    imovel_tipo: Mapped[str] = mapped_column(String(20))
    endereco_apelido: Mapped[str | None] = mapped_column(Text)
    regras_toml: Mapped[str | None] = mapped_column(Text, comment="regras.toml original")
    versao: Mapped[int] = mapped_column(Integer, comment="sobe a cada gravação")
    rascunho_desde: Mapped[int | None] = mapped_column(
        Integer,
        comment="versão salva onde o rascunho começou (None: sem rascunho); "
        "as versões acima dela são passos ainda não salvos",
    )
    hash_conteudo: Mapped[str] = mapped_column(String(64))
    versao_exportada: Mapped[int | None] = mapped_column(
        Integer, comment="versão gravada em projetos/ pela última exportação/importação"
    )
    hash_exportado: Mapped[str | None] = mapped_column(
        String(64), comment="hash dos arquivos (carregar) nessa versão"
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    pavimentos: Mapped[list[Pavimento]] = relationship(
        back_populates="projeto", cascade="all, delete-orphan", order_by="Pavimento.ordem"
    )
    medidas: Mapped[list[Medida]] = relationship(cascade="all, delete-orphan")


class _DoPavimento:
    """Colunas comuns às entidades de um pavimento."""

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    pavimento_id: Mapped[int] = mapped_column(
        ForeignKey("pavimento.id", ondelete="CASCADE"), index=True
    )
    codigo: Mapped[str] = mapped_column(Codigo)
    ordem: Mapped[int] = mapped_column(comment="posição na lista do JSON")


class Pavimento(Base):
    __tablename__ = "pavimento"
    __table_args__ = (UniqueConstraint("projeto_id", "codigo"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    projeto_id: Mapped[int] = mapped_column(ForeignKey("projeto.id", ondelete="CASCADE"))
    codigo: Mapped[str] = mapped_column(Codigo)
    ordem: Mapped[int]
    nome: Mapped[str | None] = mapped_column(Text)

    projeto: Mapped[Projeto] = relationship(back_populates="pavimentos")
    paredes: Mapped[list[Parede]] = relationship(
        cascade="all, delete-orphan", order_by="Parede.ordem"
    )
    aberturas: Mapped[list[Abertura]] = relationship(
        cascade="all, delete-orphan", order_by="Abertura.ordem"
    )
    estrutura: Mapped[list[Estrutura]] = relationship(
        cascade="all, delete-orphan", order_by="Estrutura.ordem"
    )
    instalacoes: Mapped[list[Instalacao]] = relationship(
        cascade="all, delete-orphan", order_by="Instalacao.ordem"
    )
    comodos: Mapped[list[Comodo]] = relationship(
        cascade="all, delete-orphan", order_by="Comodo.ordem"
    )


class Parede(_DoPavimento, Base):
    __tablename__ = "parede"
    __table_args__ = (UniqueConstraint("pavimento_id", "codigo"),)

    inicio_x: Mapped[int]
    inicio_y: Mapped[int]
    fim_x: Mapped[int]
    fim_y: Mapped[int]
    lado_a: Mapped[str] = mapped_column(Codigo, comment="cômodo à esquerda (início→fim)")
    lado_b: Mapped[str] = mapped_column(Codigo, comment="cômodo à direita")


class Abertura(_DoPavimento, Base):
    __tablename__ = "abertura"
    __table_args__ = (UniqueConstraint("pavimento_id", "codigo"),)

    tipo: Mapped[str] = mapped_column(String(20), comment="porta | janela")
    parede: Mapped[str] = mapped_column(Codigo)
    de: Mapped[str | None] = mapped_column(Codigo)
    para: Mapped[str | None] = mapped_column(Codigo)
    folha: Mapped[str | None] = mapped_column(String(20))
    abre_para: Mapped[str | None] = mapped_column(Codigo)
    dobradica: Mapped[str | None] = mapped_column(String(10))


class Estrutura(_DoPavimento, Base):
    __tablename__ = "estrutura"
    __table_args__ = (UniqueConstraint("pavimento_id", "codigo"),)

    tipo: Mapped[str] = mapped_column(String(20), comment="pilar | viga")
    geometria: Mapped[dict[str, Any]] = mapped_column(comment="centro ou inicio/fim")


class Instalacao(_DoPavimento, Base):
    __tablename__ = "instalacao"
    __table_args__ = (UniqueConstraint("pavimento_id", "codigo"),)

    forma: Mapped[str] = mapped_column(String(10), comment="ponto | trecho")
    tipo: Mapped[str] = mapped_column(String(20), index=True)
    posicao_x: Mapped[int | None]
    posicao_y: Mapped[int | None]
    caminho: Mapped[list[Any] | None]
    parede: Mapped[str | None] = mapped_column(Codigo)
    comodo: Mapped[str | None] = mapped_column(Codigo)
    embutido: Mapped[bool | None] = mapped_column(Boolean)
    obs: Mapped[str | None] = mapped_column(Text)


class Comodo(_DoPavimento, Base):
    __tablename__ = "comodo"
    __table_args__ = (UniqueConstraint("pavimento_id", "codigo"),)

    nome: Mapped[str] = mapped_column(Text)
    tipo: Mapped[str] = mapped_column(String(20), index=True)
    paredes: Mapped[list[str]] = mapped_column(ARRAY(String(64)))
    piso: Mapped[str | None] = mapped_column(Text)
    teto: Mapped[str | None] = mapped_column(Text)
    dados_schema_version: Mapped[int | None] = mapped_column(
        comment="schema de comodos/<id>.json; nulo se o cômodo não tem esse arquivo"
    )

    moveis: Mapped[list[Movel]] = relationship(cascade="all, delete-orphan", order_by="Movel.ordem")
    variacoes: Mapped[list[Variacao]] = relationship(
        cascade="all, delete-orphan", order_by="Variacao.codigo"
    )


class Movel(Base):
    __tablename__ = "movel"
    __table_args__ = (UniqueConstraint("comodo_id", "codigo"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    comodo_id: Mapped[int] = mapped_column(ForeignKey("comodo.id", ondelete="CASCADE"), index=True)
    codigo: Mapped[str] = mapped_column(Codigo)
    ordem: Mapped[int]
    tipo: Mapped[str] = mapped_column(String(40), index=True)
    modelo: Mapped[str | None] = mapped_column(String(40))
    nome: Mapped[str | None] = mapped_column(Text)
    centro_x: Mapped[int]
    centro_y: Mapped[int]
    rotacao: Mapped[int]
    extra: Mapped[dict[str, Any]] = mapped_column(
        comment="demais campos (portas, polegadas, construção do planejado...)"
    )


class Variacao(Base):
    __tablename__ = "variacao"
    __table_args__ = (UniqueConstraint("comodo_id", "codigo"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    comodo_id: Mapped[int] = mapped_column(ForeignKey("comodo.id", ondelete="CASCADE"))
    codigo: Mapped[str] = mapped_column(Codigo, comment="nome do arquivo da variação")
    dados: Mapped[dict[str, Any]]


class Medida(Base):
    """Medida de uma entidade (pavimento, parede, abertura, móvel...), com a origem."""

    __tablename__ = "medida"
    __table_args__ = (
        UniqueConstraint("projeto_id", "caminho"),
        Index("ix_medida_projeto_origem", "projeto_id", "origem"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    projeto_id: Mapped[int] = mapped_column(ForeignKey("projeto.id", ondelete="CASCADE"))
    caminho: Mapped[str] = mapped_column(
        Text, comment="ex.: pavimentos[terreo].paredes[p1].espessura"
    )
    pavimento: Mapped[str | None] = mapped_column(Codigo)
    comodo: Mapped[str | None] = mapped_column(Codigo, comment="só medidas do mobiliário")
    entidade: Mapped[str] = mapped_column(
        String(20), comment="projeto, pavimento, parede, abertura, comodo, instalacao, ..."
    )
    entidade_codigo: Mapped[str | None] = mapped_column(Codigo)
    campo: Mapped[str] = mapped_column(String(40))
    valor: Mapped[int] = mapped_column(comment="mm")
    origem: Mapped[str] = mapped_column(String(10), comment="trena | estimada | projeto")
    obs: Mapped[str | None] = mapped_column(Text)
    data: Mapped[date | None] = mapped_column(Date)


class Historico(Base):
    __tablename__ = "historico"
    __table_args__ = (Index("ix_historico_projeto_versao", "projeto_id", "versao"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    projeto_id: Mapped[int] = mapped_column(ForeignKey("projeto.id", ondelete="CASCADE"))
    versao: Mapped[int]
    quando: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    fonte: Mapped[str] = mapped_column(String(20), comment="api | importacao | ...")
    operacao: Mapped[str | None] = mapped_column(String(60), comment="ex.: alterar_parede")
    caminho: Mapped[str] = mapped_column(Text)
    antes: Mapped[Any | None] = mapped_column(JSONB)
    depois: Mapped[Any | None] = mapped_column(JSONB)


class Snapshot(Base):
    __tablename__ = "snapshot"
    __table_args__ = (UniqueConstraint("projeto_id", "versao"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    projeto_id: Mapped[int] = mapped_column(ForeignKey("projeto.id", ondelete="CASCADE"))
    versao: Mapped[int]
    quando: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    hash_conteudo: Mapped[str] = mapped_column(String(64))
    conteudo: Mapped[dict[str, Any]] = mapped_column(
        comment="{projeto, comodos, variacoes, regras_toml} dessa versão"
    )


class Render(Base):
    """Pedido de imagem do render (fila): status, progresso ao vivo e duração real.

    O histórico das durações alimenta a estimativa de tempo dos próximos pedidos.
    """

    __tablename__ = "render"
    __table_args__ = (Index("ix_render_projeto_comodo", "projeto_id", "comodo"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    projeto_id: Mapped[int] = mapped_column(ForeignKey("projeto.id", ondelete="CASCADE"))
    escopo: Mapped[str] = mapped_column(
        String(10),
        server_default="comodo",
        comment="comodo | pavimento (aí ``comodo`` guarda o id do pavimento)",
    )
    comodo: Mapped[str] = mapped_column(Codigo, comment="id do cômodo ou do pavimento")
    variacao: Mapped[str] = mapped_column(Codigo)
    qualidade: Mapped[str] = mapped_column(String(10), comment="rascunho | final")
    largura: Mapped[int]
    altura: Mapped[int]
    amostras: Mapped[int]
    imagens: Mapped[int] = mapped_column(comment="imagens por render (uma por vista)")
    vistas: Mapped[list[Any]] = mapped_column(
        server_default=text("""'["perspectiva", "superior"]'::jsonb"""),
        comment="câmeras pedidas (perspectiva, porta, cama, canto-N, superior)",
    )
    status: Mapped[str] = mapped_column(
        String(12), index=True, comment="na_fila | rodando | pronto | erro"
    )
    versao_projeto: Mapped[int] = mapped_column(comment="versão do projeto renderizada")
    estimativa_s: Mapped[float | None] = mapped_column(comment="estimativa ao pedir")
    progresso: Mapped[float] = mapped_column(default=0.0, comment="0 a 1")
    imagem_atual: Mapped[int | None]
    restante_s: Mapped[float | None] = mapped_column(comment="do Cycles, da imagem atual")
    duracao_s: Mapped[float | None] = mapped_column(comment="tempo real do Blender")
    em_cache: Mapped[bool] = mapped_column(Boolean, default=False)
    pasta: Mapped[str | None] = mapped_column(Text)
    arquivos: Mapped[list[Any] | None]
    erro: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    inicio: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fim: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Preferencia(Base):
    """Preferências do usuário (por ora um só: CLAUDE.md §13)."""

    __tablename__ = "preferencia"

    chave: Mapped[str] = mapped_column(String(40), primary_key=True)
    valor: Mapped[Any] = mapped_column(JSONB)
