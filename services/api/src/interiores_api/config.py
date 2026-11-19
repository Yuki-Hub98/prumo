"""Configuração da API por variáveis de ambiente (e o ``.env`` da pasta atual)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from arq.connections import RedisSettings

from interiores_banco.conexao import ler_env


def _lista(texto: str) -> list[str]:
    return [x.strip() for x in texto.split(",") if x.strip()]


@dataclass(frozen=True)
class Config:
    porta: int = 8010
    """8000 costuma estar ocupada; troque por ``API_PORT``."""
    host: str = "127.0.0.1"
    """Só a própria máquina; no Docker use ``API_HOST=0.0.0.0``."""
    pasta_projetos: Path = Path("projetos")
    exportar: bool = True
    """Reexporta ``projetos/<p>/`` a cada edição (JSON = exportação versionada do banco)."""
    cors: list[str] = field(default_factory=lambda: ["http://localhost:5173"])
    banco_url: str | None = None
    """Sem valor, usa ``INTERIORES_BANCO_URL`` / ``POSTGRES_*``."""
    redis_host: str = "localhost"
    redis_porta: int = 6379

    @property
    def redis(self) -> RedisSettings:
        return RedisSettings(host=self.redis_host, port=self.redis_porta)

    @classmethod
    def do_ambiente(cls) -> Config:
        env = {**ler_env(), **os.environ}
        return cls(
            porta=int(env.get("API_PORT", "8010")),
            host=env.get("API_HOST", "127.0.0.1"),
            pasta_projetos=Path(env.get("INTERIORES_PROJETOS", "projetos")),
            exportar=env.get("INTERIORES_API_EXPORTAR", "1") not in ("0", "false", "nao"),
            cors=_lista(env.get("API_CORS_ORIGENS", "http://localhost:5173")),
            banco_url=env.get("INTERIORES_BANCO_URL"),
            redis_host=env.get("REDIS_HOST", "localhost"),
            redis_porta=int(env.get("REDIS_PORT", "6379")),
        )
