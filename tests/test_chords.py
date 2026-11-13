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


def test_single_note_tie_among_many_chords_still_prefers_key():
    """Só a nota do pico soa: seis tríades empatam, e a do tom (F ou Dm em Dó maior) vence."""
    only_f = [0.0] * 12
    only_f[5] = 1.0
    assert moment_chord([only_f] * 3, (0, "maior")) in {"F", "Dm"}


def _with_seventh(root: int, seventh_weight: float) -> list[float]:
    """Tríade maior com a sétima menor (10 semitons acima da raiz) no peso dado."""
    chroma = _triad(root)
    chroma[(root + 10) % 12] = seventh_weight
    return chroma


def test_dominant_seventh_wins_on_the_key_dominant():
    """B7 em Mi menor: a sétima (A) só aparece com peso médio, e ainda assim vira B7."""
    assert moment_chord([_with_seventh(11, 0.55)] * 3, (4, "menor")) == "B7"


def test_weak_seventh_stays_triad_even_on_the_dominant():
    assert moment_chord([_with_seventh(11, 0.3)] * 3, (4, "menor")) == "B"


def test_seventh_off_the_dominant_needs_a_clear_note():
    c_with_passing_seventh = _with_seventh(0, 0.55)
    assert moment_chord([c_with_passing_seventh] * 3, (4, "menor")) == "C"
    assert moment_chord([_with_seventh(0, 0.9)] * 3, (4, "menor")) == "C7"


def test_transpose_dominant_seventh():
    assert transpose_chord("B7", 1) == "C7"
    assert transpose_chord("F#7", -5) == "C#7"
