from app.domain.chords import moment_chord, transpose_chord


def _triad(root: int, minor: bool = False) -> list[float]:
    """Chroma sintético de uma tríade: raiz, terça e quinta fortes sobre um piso baixo."""
    chroma = [0.05] * 12
    for step in (0, 3 if minor else 4, 7):
        chroma[(root + step) % 12] = 1.0
    return chroma


def _near_tie() -> list[float]:
    """Chroma entre Em (G forte) e E (G# quase tão forte); Em ganha por pouco."""
    chroma = [0.05] * 12
    chroma[4], chroma[11], chroma[7], chroma[8] = 1.0, 1.0, 0.5, 0.48
    return chroma


def test_moment_names_minor_and_major():
    assert moment_chord([_triad(4, minor=True)] * 3, None) == "Em"
    assert moment_chord([_triad(6)] * 3, None) == "F#"


def test_moment_takes_most_frequent_window():
    em, g = _triad(4, minor=True), _triad(7)
    assert moment_chord([em, em, g], None) == "Em"


def test_near_tie_prefers_key_chord():
    windows = [_near_tie()] * 3
    assert moment_chord(windows, None) == "Em"
    assert moment_chord(windows, (4, "maior")) == "E"
    assert moment_chord(windows, (4, "menor")) == "Em"


def test_clear_winner_ignores_key():
    assert moment_chord([_triad(6)] * 3, (0, "maior")) == "F#"


def test_silent_windows_give_no_chord():
    assert moment_chord([[0.0] * 12] * 3, None) is None


def test_transpose_chord():
    assert transpose_chord("Em", 3) == "Gm"
    assert transpose_chord("B", 1) == "C"
    assert transpose_chord("C", -1) == "B"
    assert transpose_chord("F#m", -5) == "C#m"
