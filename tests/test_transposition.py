from app.domain.transposition import scale_degree, shift_semitones, transpose_tonic


def test_shift_b4_to_f_sharp4_is_minus_five():
    assert shift_semitones(71, 66) == -5


def test_g_down_five_is_d():
    assert transpose_tonic(7, -5) == 2


def test_scale_degree_b_in_g_is_third():
    assert scale_degree(71, 7) == "3ª"


def test_shift_never_goes_above_the_ceiling():
    # A#4 com teto C#4: desce 9 semitons (C#4) em vez de subir 3 (C#5, acima do teto).
    assert shift_semitones(70, 61) == -9


def test_shift_is_zero_when_top_is_already_at_the_ceiling_pitch():
    assert shift_semitones(66, 66) == 0
    assert shift_semitones(78, 66) == 0


def test_shift_range_edges():
    for diff in range(24):
        assert -11 <= shift_semitones(60, 60 + diff) <= 0
