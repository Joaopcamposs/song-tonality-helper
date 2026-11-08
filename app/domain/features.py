"""Valores puros da análise de áudio, sem libs de áudio: versão do critério e resultado."""

from dataclasses import dataclass

# Sobe quando o critério da análise muda, para refazer os registros guardados.
ALGO_VERSION = 2

# Duração de cada janela do chroma guardado; o tom é detectado janela a janela.
CHROMA_WINDOW_SECONDS = 10.0


@dataclass(frozen=True)
class AudioFeatures:
    """Resultado da análise: topo da melodia, ranking, tempos e o chroma por janela."""

    top_midi: int
    ranking: list[tuple[int, int]]
    top_times: list[float]
    chroma_windows: list[list[float]]  # uma janela de CHROMA_WINDOW_SECONDS por item, 12 notas
