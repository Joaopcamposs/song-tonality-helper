"""Detecção do tom por correlação do chroma com os perfis de Krumhansl-Kessler."""

from dataclasses import dataclass
from typing import Literal

import numpy as np

_MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
_MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


@dataclass(frozen=True)
class KeyCandidate:
    """Um tom candidato com a correlação obtida (quanto maior, mais provável)."""

    tonic_pc: int
    mode: Literal["maior", "menor"]
    score: float


def detect_key(chroma: np.ndarray) -> list[KeyCandidate]:
    """Os 3 tons mais prováveis para um chroma de 12 linhas, do melhor para o pior."""
    profile = chroma.mean(axis=1)
    candidates: list[KeyCandidate] = []
    for mode, reference in (("maior", _MAJOR), ("menor", _MINOR)):
        for tonic_pc in range(12):
            score = float(np.corrcoef(profile, np.roll(reference, tonic_pc))[0, 1])
            candidates.append(KeyCandidate(tonic_pc, mode, score))
    return sorted(candidates, key=lambda c: c.score, reverse=True)[:3]
