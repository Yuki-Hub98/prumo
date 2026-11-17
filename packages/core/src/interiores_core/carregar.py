"""Leitura de ``projetos/<projeto>/``: ``projeto.json`` + ``comodos/*.json``."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from interiores_core.geometria import recorte_do_comodo
from interiores_core.medidas import Medida, medidas_estimadas
from interiores_core.modelo import DadosComodo, Projeto


@dataclass(frozen=True)
class ProjetoCarregado:
    """Projeto validado pelo pydantic, com os dados de cada cômodo e o hash da entrada."""

    pasta: Path
    projeto: Projeto
    dados_comodos: dict[str, DadosComodo] = field(default_factory=dict)
    hash_entrada: str = ""

    @property
    def hash_curto(self) -> str:
        """Hash curto para o carimbo dos desenhos."""
        return self.hash_entrada[:10]

    def estimadas(self, comodo: str | None = None) -> list[tuple[str, Medida]]:
        """Medidas estimadas do projeto, ou só do pavimento + cômodo indicado.

        No escopo de cômodo entram as do pavimento que tocam o cômodo (pé-direito,
        rodapé, suas paredes, aberturas nelas, instalações e estrutura dentro ou na
        borda) e as do mobiliário daquele cômodo.
        """
        if comodo is None:
            achadas = medidas_estimadas(self.projeto)
            for nome, dados in sorted(self.dados_comodos.items()):
                achadas += medidas_estimadas(dados, f"comodos/{nome}")
            return achadas
        pav = self.projeto.pavimento_do_comodo(comodo)
        if pav is None:
            raise KeyError(f"cômodo '{comodo}' não existe no projeto")
        recorte = recorte_do_comodo(pav, comodo)
        achadas = medidas_estimadas(recorte, f"pavimentos[{pav.id}]")
        if comodo in self.dados_comodos:
            achadas += medidas_estimadas(self.dados_comodos[comodo], f"comodos/{comodo}")
        return achadas


def _ler_json(caminho: Path) -> object:
    with caminho.open(encoding="utf-8") as f:
        return json.load(f)


def _canonico(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def carregar(pasta: Path | str) -> ProjetoCarregado:
    """Carrega e valida o formato de um projeto.

    Levanta ``pydantic.ValidationError`` se o JSON não seguir o schema e
    ``FileNotFoundError`` se faltar o ``projeto.json``. Consistência entre
    elementos é checada depois, com :func:`interiores_core.validacao.validar`.

    O hash da entrada é calculado sobre o conteúdo canônico (chaves ordenadas)
    de todos os JSON lidos, então reformatar o arquivo não muda o hash.
    """
    pasta = Path(pasta)
    bruto = _ler_json(pasta / "projeto.json")
    projeto = Projeto.model_validate(bruto)
    hash_ = hashlib.sha256(b"projeto.json\0" + _canonico(bruto))

    dados: dict[str, DadosComodo] = {}
    pasta_comodos = pasta / "comodos"
    if pasta_comodos.is_dir():
        for arquivo in sorted(pasta_comodos.glob("*.json")):
            conteudo = _ler_json(arquivo)
            dados[arquivo.stem] = DadosComodo.model_validate(conteudo)
            hash_.update(f"\0comodos/{arquivo.name}\0".encode() + _canonico(conteudo))

    return ProjetoCarregado(
        pasta=pasta, projeto=projeto, dados_comodos=dados, hash_entrada=hash_.hexdigest()
    )
