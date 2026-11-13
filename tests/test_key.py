from app.domain.features import CHROMA_WINDOW_SECONDS
from app.domain.key import detect_key, key_sections


def _chroma_for(weights: dict[int, float]) -> list[float]:
    profile = [0.05] * 12
    for pc, weight in weights.items():
        profile[pc] = weight
    return profile


def test_detects_g_major():
    # Escala de G maior com ênfase em G, B e D (tônica, terça e quinta).
    chroma = _chroma_for({7: 1.0, 11: 0.8, 2: 0.9, 9: 0.4, 0: 0.5, 4: 0.5, 6: 0.3})
    best = detect_key(chroma)[0]
    assert (best.tonic_pc, best.mode) == (7, "maior")


def test_returns_three_candidates():
    chroma = _chroma_for({0: 1.0, 4: 0.8, 7: 0.9})
    assert len(detect_key(chroma)) == 3


def _window_in(tonic_pc: int) -> list[float]:
    """Janela de chroma de uma tríade maior mais a escala, com o tom em `tonic_pc`."""
    return _chroma_for({(tonic_pc + step) % 12: weight for step, weight in _E_MAJOR_STEPS.items()})


_E_MAJOR_STEPS = {0: 1.0, 2: 0.5, 4: 0.8, 5: 0.3, 7: 0.9, 9: 0.5, 11: 0.5}


def test_modulation_gives_two_sections():
    # Como "Estrelinha": começa em E (4) e sobe um tom para F# (6) na metade.
    windows = [_window_in(4)] * 6 + [_window_in(6)] * 6
    sections = key_sections(windows)
    assert [(s.start, s.tonic_pc, s.mode) for s in sections] == [
        (0.0, 4, "maior"),
        (6 * CHROMA_WINDOW_SECONDS, 6, "maior"),
    ]


def test_single_key_gives_one_section():
    sections = key_sections([_window_in(4)] * 5)
    assert [(s.start, s.tonic_pc) for s in sections] == [(0.0, 4)]


def test_short_detour_does_not_open_a_section():
    # Uma janela solta em outro tom (empréstimo de acorde) não conta como modulação.
    windows = [_window_in(4)] * 4 + [_window_in(11)] + [_window_in(4)] * 4
    assert [s.tonic_pc for s in key_sections(windows)] == [4]


def test_unclear_windows_keep_the_previous_key():
    # Silêncio no meio (perfil plano) herda o tom de antes em vez de abrir trecho novo.
    windows = [_window_in(4)] * 3 + [[0.0] * 12] * 2 + [_window_in(4)] * 3
    assert [s.tonic_pc for s in key_sections(windows)] == [4]


def test_all_unclear_still_returns_one_section():
    assert len(key_sections([[0.1] * 12] * 3)) == 1


def test_relative_shown_when_close():
    # Escala de C com ênfase em A, E e C: Lá menor e Dó maior ficam próximos.
    windows = [_chroma_for({9: 1.0, 0: 0.9, 4: 0.9, 2: 0.7, 11: 0.7, 5: 0.5, 7: 0.5})] * 3
    section = key_sections(windows)[0]
    relative = section.relative
    assert relative is not None
    pair = {(section.tonic_pc, section.mode), (relative.tonic_pc, relative.mode)}
    assert pair == {(0, "maior"), (9, "menor")}


def test_relative_hidden_when_clear():
    # Uma tríade maior bem definida não deixa o relativo perto.
    section = key_sections([_window_in(4)] * 3)[0]
    assert section.relative is None


def test_tie_goes_to_the_relative_with_the_stronger_dominant():
    # Mesmas notas de C/Lá menor: com E (dominante de Lá) bem acima de G, vence Lá menor.
    base = {0: 1.0, 9: 0.9, 2: 0.7, 11: 0.7, 5: 0.5}
    a_minor = key_sections([_chroma_for({**base, 4: 1.0, 7: 0.5})] * 3)[0]
    c_major = key_sections([_chroma_for({**base, 4: 0.5, 7: 1.0})] * 3)[0]
    assert (a_minor.tonic_pc, a_minor.mode) == (9, "menor")
    assert (c_major.tonic_pc, c_major.mode) == (0, "maior")


def test_excursion_that_returns_is_not_a_modulation():
    # Dois trechos em outro tom (ênfase na dominante) e a volta ao tom de antes: segue um tom só.
    windows = [_window_in(7)] * 7 + [_window_in(2)] * 2 + [_window_in(7)] * 5
    assert [s.tonic_pc for s in key_sections(windows)] == [7]


def test_long_stay_in_another_key_that_returns_is_still_a_modulation():
    windows = [_window_in(7)] * 5 + [_window_in(2)] * 4 + [_window_in(7)] * 5
    assert [s.tonic_pc for s in key_sections(windows)] == [7, 2, 7]
