from app.domain.transposition import scale_degree, shift_semitones, transpose_tonic


def test_shift_b4_to_f_sharp4_is_minus_five():
    assert shift_semitones(71, 66) == -5


def test_g_down_five_is_d():
    assert transpose_tonic(7, -5) == 2


def test_scale_degree_b_in_g_is_third():
    assert scale_degree(71, 7) == "3ª"


def test_shift_range_edges():
    for diff in range(24):
        assert -6 <= shift_semitones(60, 60 + diff) <= 5
