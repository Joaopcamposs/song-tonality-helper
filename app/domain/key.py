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
MAX_EXCURSION_WINDOWS = 2  # trecho assim de curto que volta ao tom anterior é ênfase, não modulação
DOMINANT_MARGIN = 0.15  # dominante do relativo precisa ser 15% mais forte para ele vencer o empate
MAX_RELATIVE_GAP = 0.2  # o relativo só vira alternativa se ficar a no máximo isso do tom escolhido


@dataclass(frozen=True)
class KeyCandidate:
    """Um tom candidato com a correlação obtida (quanto maior, mais provável)."""

    tonic_pc: int
    mode: Literal["maior", "menor"]
    score: float


def _score(profile: np.ndarray, tonic_pc: int, mode: Literal["maior", "menor"]) -> float:
    """Correlação do perfil de 12 notas com o modelo do tom; 0 para perfil plano (silêncio)."""
    if np.ptp(profile) == 0:
        return 0.0
    reference = _MAJOR if mode == "maior" else _MINOR
    return float(np.corrcoef(profile, np.roll(reference, tonic_pc))[0, 1])


def detect_key(chroma_profile: Sequence[float]) -> list[KeyCandidate]:
    """Os 3 tons mais prováveis para o perfil médio de 12 notas, do melhor para o pior."""
    profile = np.asarray(chroma_profile, dtype=float)
    candidates = [
        KeyCandidate(tonic_pc, mode, _score(profile, tonic_pc, mode))
        for mode in ("maior", "menor")
        for tonic_pc in range(12)
    ]
    return sorted(candidates, key=lambda c: c.score, reverse=True)[:3]


def _relative(key: KeyCandidate) -> tuple[int, Literal["maior", "menor"]]:
    """Tom relativo: mesmas sete notas, outra tônica (C maior e Lá menor, por exemplo)."""
    if key.mode == "maior":
        return (key.tonic_pc + 9) % 12, "menor"
    return (key.tonic_pc + 3) % 12, "maior"


@dataclass(frozen=True)
class KeySection:
    """Um trecho da música num mesmo tom, com o segundo em que ele começa."""

    start: float
    tonic_pc: int
    mode: Literal["maior", "menor"]
    score: float
    relative: KeyCandidate | None = None  # relativo quase tão provável quanto o tom escolhido


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


def _section(
    start: float, key: KeyCandidate, score: float, profiles: list[np.ndarray]
) -> KeySection:
    """Monta o trecho; guarda o relativo se, nas mesmas janelas, ele ficar perto do tom."""
    tonic_pc, mode = _relative(key)
    relative_score = float(np.mean([_score(p, tonic_pc, mode) for p in profiles]))
    if score - relative_score > MAX_RELATIVE_GAP:
        return KeySection(start, key.tonic_pc, key.mode, score)
    mean = np.mean(profiles, axis=0)  # empate: vence o tom cuja dominante (quinta) soa mais forte
    if mean[(tonic_pc + 7) % 12] > mean[(key.tonic_pc + 7) % 12] * (1 + DOMINANT_MARGIN):
        chosen = KeyCandidate(key.tonic_pc, key.mode, score)
        return KeySection(start, tonic_pc, mode, relative_score, chosen)
    return KeySection(
        start, key.tonic_pc, key.mode, score, KeyCandidate(tonic_pc, mode, relative_score)
    )


def key_sections(windows: Sequence[Sequence[float]]) -> list[KeySection]:
    """Trechos da música por tom, em ordem; uma música sem modulação dá um trecho só."""
    bests = [detect_key(window)[0] for window in windows]
    clear = [best if best.score >= MIN_SCORE else None for best in bests]
    if not any(clear):  # nada claro (silêncio, ruído): vale o perfil médio da música toda
        best = detect_key(np.mean(np.asarray(windows, dtype=float), axis=0).tolist())[0]
        mean = np.mean(np.asarray(windows, dtype=float), axis=0)
        return [_section(0.0, best, best.score, [mean])]

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
    settled: list[_Run] = []
    for run in merged:
        short_detour = len(settled) >= 2 and settled[-1].windows <= MAX_EXCURSION_WINDOWS
        if short_detour and settled[-2].same_key(run.best):
            excursion = settled.pop()
            settled[-1].windows += excursion.windows + run.windows
            settled[-1].scores += run.scores
        else:
            settled.append(run)
    merged = settled
    while len(merged) > 1 and merged[0].windows < MIN_SECTION_WINDOWS:  # curto logo no começo
        merged[1].first_window = merged[0].first_window
        merged[1].windows += merged[0].windows
        merged.pop(0)

    sections = [
        _section(
            run.first_window * CHROMA_WINDOW_SECONDS,
            run.best,
            float(np.mean(run.scores)),
            [np.asarray(w, dtype=float) for w in windows[run.first_window :][: run.windows]],
        )
        for run in merged
    ]
    # O desempate pode igualar vizinhos (C e Lá menor viram Lá menor): não é modulação.
    unique = [sections[0]]
    for section in sections[1:]:
        if (section.tonic_pc, section.mode) != (unique[-1].tonic_pc, unique[-1].mode):
            unique.append(section)
    return unique
