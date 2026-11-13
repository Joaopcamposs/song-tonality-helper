from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from app.domain.errors import NoMelodyError
from app.domain.features import ALGO_VERSION
from app.domain.key import KeySection
from app.domain.pitch import HOP, SAMPLE_RATE, _chords_at, analyze_audio, rank_notes


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


def test_chroma_comes_in_windows_of_twelve_notes(make_wav):
    features = analyze_audio(make_wav([(67, 30)]))
    assert len(features.chroma_windows) == 3  # 30 s em janelas de 10 s
    assert all(len(window) == 12 for window in features.chroma_windows)
    assert all(isinstance(v, float) for window in features.chroma_windows for v in window)


def test_short_audio_still_has_one_window(make_wav):
    assert len(analyze_audio(make_wav([(67, 8)])).chroma_windows) == 1


def test_algo_version_is_defined():
    assert ALGO_VERSION == 3


def test_silence_raises_no_melody(make_wav):
    with pytest.raises(NoMelodyError):
        analyze_audio(make_wav([(None, 5)]))


def test_sparse_high_notes_do_not_hide_the_sustained_top():
    # Contagens reais de "Caso Indefinido": as 8 notas mais altas são esparsas (< 100 quadros).
    counts = {78: 1, 77: 7, 76: 22, 75: 30, 74: 5, 73: 92, 72: 9, 71: 72, 70: 10, 68: 356, 64: 815}
    top, ranking = rank_notes(list(counts), list(counts.values()))
    assert top == 68
    assert ranking == [(68, 356), (64, 815)]


def _chord_wav(tmp_path: Path, melody: list[tuple[int, float]]) -> Path:
    """Wav com a melodia dada sobre um acorde de Mi menor (E3, G3, B3) mais baixo e constante."""
    rng = np.random.default_rng(0)

    def tone(midi: int, t: np.ndarray) -> np.ndarray:
        freq = 440.0 * 2 ** ((midi - 69) / 12)
        return sum(np.sin(2 * np.pi * freq * h * t) / h for h in (1, 2, 3))

    t_melody = [np.arange(int(SAMPLE_RATE * seconds)) / SAMPLE_RATE for _, seconds in melody]
    lead = np.concatenate([tone(midi, t) for (midi, _), t in zip(melody, t_melody, strict=True)])
    t_all = np.arange(lead.size) / SAMPLE_RATE
    drone = sum(0.15 * tone(midi, t_all) for midi in (52, 55, 59))
    audio = lead + drone + rng.normal(0, 0.3, lead.size)
    path = tmp_path / "chord.wav"
    sf.write(path, 0.5 * audio / np.abs(audio).max(), SAMPLE_RATE)
    return path


def test_top_chords_parallel_to_top_times_and_name_the_chord(tmp_path):
    features = analyze_audio(_chord_wav(tmp_path, [(67, 10), (71, 10), (62, 10)]))
    assert features.top_midi == 71
    assert len(features.top_chords) == len(features.top_times)
    assert features.top_chords[0] == "Em"


def test_peak_at_edges_still_gets_a_chord():
    chroma = np.full((12, round(20 * SAMPLE_RATE / HOP)), 0.05)
    chroma[4], chroma[7], chroma[11] = 1.0, 1.0, 1.0  # Em do começo ao fim
    sections = [KeySection(0.0, 4, "menor", 1.0)]
    assert _chords_at(chroma, [0.0, 19.9], sections) == ["Em", "Em"]


def test_peak_uses_key_of_its_own_section():
    chroma = np.full((12, round(40 * SAMPLE_RATE / HOP)), 0.05)
    chroma[4], chroma[11], chroma[7], chroma[8] = 1.0, 1.0, 0.5, 0.48  # quase empate E / Em
    sections = [KeySection(0.0, 0, "maior", 1.0), KeySection(30.0, 4, "maior", 1.0)]
    assert _chords_at(chroma, [5.0, 35.0], sections) == ["Em", "E"]
