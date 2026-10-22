import pytest

from app.domain.errors import NoMelodyError
from app.domain.pitch import ALGO_VERSION, analyze_audio, rank_notes


def test_top_note_is_highest_sustained(make_wav):
    features = analyze_audio(make_wav([(67, 10), (71, 10), (62, 10)]))
    assert features.top_midi == 71
    assert features.ranking[0][0] == 71


def test_short_blip_is_ignored(make_wav):
    features = analyze_audio(make_wav([(67, 10), (76, 0.2), (67, 10)]))
    assert features.top_midi == 67


def test_top_times_point_to_where_note_plays(make_wav):
    features = analyze_audio(make_wav([(67, 10), (71, 10), (62, 10)]))
    assert features.top_times
    assert all(9.5 <= t <= 20.5 for t in features.top_times)


def test_chroma_profile_has_twelve_values(make_wav):
    features = analyze_audio(make_wav([(67, 10)]))
    assert len(features.chroma_profile) == 12
    assert all(isinstance(v, float) for v in features.chroma_profile)


def test_algo_version_is_defined():
    assert ALGO_VERSION == 1


def test_silence_raises_no_melody(make_wav):
    with pytest.raises(NoMelodyError):
        analyze_audio(make_wav([(None, 5)]))


def test_sparse_high_notes_do_not_hide_the_sustained_top():
    # Contagens reais de "Caso Indefinido": as 8 notas mais altas são esparsas (< 100 quadros).
    counts = {78: 1, 77: 7, 76: 22, 75: 30, 74: 5, 73: 92, 72: 9, 71: 72, 70: 10, 68: 356, 64: 815}
    top, ranking = rank_notes(list(counts), list(counts.values()))
    assert top == 68
    assert ranking == [(68, 356), (64, 815)]
