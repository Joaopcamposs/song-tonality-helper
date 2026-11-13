"""Acorde provável de um momento da música: tríades maiores e menores a partir do chroma."""

from collections import Counter
from collections.abc import Sequence
from typing import Literal

import numpy as np

from app.domain.notes import NOTE_NAMES

WINDOW_SECONDS = 0.5  # cada janela recebe um acorde
BEFORE_SECONDS = 0.5  # o momento começa um pouco antes do instante da nota
AFTER_SECONDS = 3.0  # e segue depois dele, para pegar o acorde que sustenta a nota

# Diferença de correlação abaixo da qual os dois melhores acordes contam como empatados.
TIE_MARGIN = 0.05

# Tríades do campo harmônico: (semitons acima da tônica, é menor). O menor inclui o V maior.
_MAJOR_KEY = {(0, False), (2, True), (4, True), (5, False), (7, False), (9, True)}
_MINOR_KEY = {(0, True), (3, False), (5, True), (7, True), (7, False), (8, False), (10, False)}

Chord = tuple[int, bool]  # (raiz como classe de altura, é menor)


def _template(chord: Chord) -> np.ndarray:
    """Modelo binário da tríade: raiz, terça (maior ou menor) e quinta."""
    root, minor = chord
    vector = np.zeros(12)
    for step in (0, 3 if minor else 4, 7):
        vector[(root + step) % 12] = 1.0
    return vector


_CHORDS: list[Chord] = [(root, minor) for minor in (False, True) for root in range(12)]
_TEMPLATES = [_template(chord) for chord in _CHORDS]


def _name(chord: Chord) -> str:
    """Nome do acorde com sustenido, ex.: `F#` ou `C#m`."""
    root, minor = chord
    return NOTE_NAMES[root] + ("m" if minor else "")


def _in_key(chord: Chord, key: tuple[int, Literal["maior", "menor"]]) -> bool:
    """Se a tríade pertence ao campo harmônico do tom."""
    tonic, mode = key
    degrees = _MAJOR_KEY if mode == "maior" else _MINOR_KEY
    return ((chord[0] - tonic) % 12, chord[1]) in degrees


def _best(
    window: Sequence[float], key: tuple[int, Literal["maior", "menor"]] | None
) -> tuple[Chord, float] | None:
    """Melhor tríade da janela e sua correlação; `None` se a janela for silenciosa."""
    vector = np.asarray(window, dtype=float)
    norm = np.linalg.norm(vector)
    if norm == 0:
        return None
    scores = [float(t @ vector / (np.linalg.norm(t) * norm)) for t in _TEMPLATES]
    order = [int(i) for i in np.argsort(scores)[::-1]]
    first = order[0]
    if key and not _in_key(_CHORDS[first], key):
        # Empate: vence o acorde do tom de maior correlação entre os que ficam na margem.
        tied = (i for i in order if scores[first] - scores[i] < TIE_MARGIN)
        first = next((i for i in tied if _in_key(_CHORDS[i], key)), first)
    return _CHORDS[first], scores[first]


def moment_chord(
    windows: Sequence[Sequence[float]], key: tuple[int, Literal["maior", "menor"]] | None
) -> str | None:
    """Acorde mais frequente entre as janelas (chroma de 12 notas); `key` só desempata.

    Empate de votos vai para o acorde de maior correlação somada. Sem janela com som, `None`.
    """
    votes: Counter[Chord] = Counter()
    total: dict[Chord, float] = {}
    for window in windows:
        best = _best(window, key)
        if best is None:
            continue
        chord, score = best
        votes[chord] += 1
        total[chord] = total.get(chord, 0.0) + score
    if not votes:
        return None
    return _name(max(votes, key=lambda c: (votes[c], total[c])))


def transpose_chord(name: str, shift: int) -> str:
    """Nome do acorde depois de somar `shift` semitons à raiz, mantendo maior ou menor."""
    minor = name.endswith("m")
    root = NOTE_NAMES.index(name.removesuffix("m"))
    return _name(((root + shift) % 12, minor))
