"""Acorde provável de um momento: tríades maiores, menores e dominantes com sétima (chroma)."""

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

# Sétima dominante só ganha força fora do V do tom se a sétima soar com clareza.
SEVENTH_PENALTY = 0.95

Chord = tuple[int, str]  # (raiz como classe de altura, tipo: "" maior, "m" menor, "7" dominante)

_STEPS = {"": (0, 4, 7), "m": (0, 3, 7), "7": (0, 4, 7, 10)}


def _template(chord: Chord) -> np.ndarray:
    """Modelo binário do acorde: raiz, terça, quinta e, no tipo `7`, a sétima menor."""
    root, kind = chord
    vector = np.zeros(12)
    for step in _STEPS[kind]:
        vector[(root + step) % 12] = 1.0
    return vector


_CHORDS: list[Chord] = [(root, kind) for kind in _STEPS for root in range(12)]
_TEMPLATES = [_template(chord) for chord in _CHORDS]


def _name(chord: Chord) -> str:
    """Nome do acorde com sustenido, ex.: `F#`, `C#m` ou `B7`."""
    root, kind = chord
    return NOTE_NAMES[root] + kind


def _is_dominant(chord: Chord, key: tuple[int, Literal["maior", "menor"]] | None) -> bool:
    """Se a raiz do acorde é o V do tom (vale para maior e menor)."""
    return key is not None and chord[0] == (key[0] + 7) % 12


def _in_key(chord: Chord, key: tuple[int, Literal["maior", "menor"]]) -> bool:
    """Se o acorde pertence ao campo harmônico do tom; só o V conta com sétima."""
    if chord[1] == "7":
        return _is_dominant(chord, key)
    tonic, mode = key
    degrees = _MAJOR_KEY if mode == "maior" else _MINOR_KEY
    return ((chord[0] - tonic) % 12, chord[1] == "m") in degrees


def _best(
    window: Sequence[float], key: tuple[int, Literal["maior", "menor"]] | None
) -> tuple[Chord, float] | None:
    """Melhor acorde da janela e sua correlação; `None` se a janela for silenciosa."""
    vector = np.asarray(window, dtype=float)
    norm = np.linalg.norm(vector)
    if norm == 0:
        return None
    scores = [float(t @ vector / (np.linalg.norm(t) * norm)) for t in _TEMPLATES]
    for i, chord in enumerate(_CHORDS):
        if chord[1] == "7" and not _is_dominant(chord, key):
            scores[i] *= SEVENTH_PENALTY
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
    """Nome do acorde depois de somar `shift` semitons à raiz, mantendo o tipo."""
    kind = name[-1] if name.endswith(("m", "7")) else ""
    root = NOTE_NAMES.index(name.removesuffix(kind))
    return _name(((root + shift) % 12, kind))
