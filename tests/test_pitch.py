import pytest

from app.domain.errors import NoMelodyError
from app.domain.pitch import analyze_audio


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


def test_chroma_has_twelve_rows(make_wav):
    features = analyze_audio(make_wav([(67, 10)]))
    assert features.chroma.shape[0] == 12


def test_silence_raises_no_melody(make_wav):
    with pytest.raises(NoMelodyError):
        analyze_audio(make_wav([(None, 5)]))
