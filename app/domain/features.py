"""Valores puros da análise de áudio, sem libs de áudio: versão do critério e resultado."""

from dataclasses import dataclass

# Sobe quando o critério da análise muda, para refazer os registros guardados.
ALGO_VERSION = 1


@dataclass(frozen=True)
class AudioFeatures:
    """Resultado da análise: topo da melodia, ranking, tempos e perfil médio do chroma."""

    top_midi: int
    ranking: list[tuple[int, int]]
    top_times: list[float]
    chroma_profile: list[float]  # média do chroma no tempo: 12 valores, um por nota
