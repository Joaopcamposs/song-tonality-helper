"""Detecção do tom e das modulações: correlação do chroma com os perfis de Krumhansl-Kessler."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

import numpy as np

from app.domain.features import CHROMA_WINDOW_SECONDS

_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

MIN_SCORE = 0.5  # janela com correlação menor que isso (silêncio, ruído) não decide o tom
MIN_SECTION_WINDOWS = 2  # trecho menor que isso é empréstimo de acorde, não modulação


@dataclass(frozen=True)
class KeyCandidate:
    """Um tom candidato com a correlação obtida (quanto maior, mais provável)."""

    tonic_pc: int
    mode: Literal["maior", "menor"]
    score: float


def detect_key(chroma_profile: Sequence[float]) -> list[KeyCandidate]:
    """Os 3 tons mais prováveis para o perfil médio de 12 notas, do melhor para o pior."""
    profile = np.asarray(chroma_profile, dtype=float)
    candidates: list[KeyCandidate] = []
    for mode, reference in (("maior", _MAJOR), ("menor", _MINOR)):
        for tonic_pc in range(12):
            if np.ptp(profile) == 0:  # perfil plano (silêncio): sem correlação possível
                score = 0.0
            else:
                score = float(np.corrcoef(profile, np.roll(reference, tonic_pc))[0, 1])
            candidates.append(KeyCandidate(tonic_pc, mode, score))
    return sorted(candidates, key=lambda c: c.score, reverse=True)[:3]


@dataclass(frozen=True)
class KeySection:
    """Um trecho da música num mesmo tom, com o segundo em que ele começa."""

    start: float
    tonic_pc: int
    mode: Literal["maior", "menor"]
    score: float


@dataclass
class _Run:
    """Janelas seguidas num mesmo tom, enquanto os trechos são montados."""

    best: KeyCandidate
    first_window: int
    windows: int
    scores: list[float]

    def same_key(self, other: KeyCandidate) -> bool:
        """Se o candidato tem o mesmo tom (tônica e modo) do trecho."""
        return (self.best.tonic_pc, self.best.mode) == (other.tonic_pc, other.mode)


def key_sections(windows: Sequence[Sequence[float]]) -> list[KeySection]:
    """Trechos da música por tom, em ordem; uma música sem modulação dá um trecho só."""
    bests = [detect_key(window)[0] for window in windows]
    clear = [best if best.score >= MIN_SCORE else None for best in bests]
    if not any(clear):  # nada claro (silêncio, ruído): vale o perfil médio da música toda
        best = detect_key(np.mean(np.asarray(windows, dtype=float), axis=0).tolist())[0]
        return [KeySection(0.0, best.tonic_pc, best.mode, best.score)]

    # Janela sem tom claro herda o da vizinha anterior (ou da primeira clara, no começo).
    labels: list[KeyCandidate] = []
    first = next(c for c in clear if c is not None)
    for candidate in clear:
        labels.append(candidate or (labels[-1] if labels else first))

    runs: list[_Run] = []
    for index, label in enumerate(labels):
        if runs and runs[-1].same_key(label):
            runs[-1].windows += 1
            runs[-1].scores.append(label.score)
        else:
            runs.append(_Run(label, index, 1, [label.score]))

    # Trecho curto demais vira parte do anterior; vizinhos de mesmo tom se fundem.
    merged: list[_Run] = []
    for run in runs:
        if merged and run.windows < MIN_SECTION_WINDOWS:
            merged[-1].windows += run.windows
        elif merged and merged[-1].same_key(run.best):
            merged[-1].windows += run.windows
            merged[-1].scores += run.scores
        else:
            merged.append(run)
    while len(merged) > 1 and merged[0].windows < MIN_SECTION_WINDOWS:  # curto logo no começo
        merged[1].first_window = merged[0].first_window
        merged[1].windows += merged[0].windows
        merged.pop(0)

    return [
        KeySection(
            start=run.first_window * CHROMA_WINDOW_SECONDS,
            tonic_pc=run.best.tonic_pc,
            mode=run.best.mode,
            score=float(np.mean(run.scores)),
        )
        for run in merged
    ]
