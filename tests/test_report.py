from app.domain.features import AudioFeatures
from app.services.report import build_report


def _g_major_features() -> AudioFeatures:
    profile = [0.05] * 12
    for pc, weight in {7: 1.0, 11: 0.8, 2: 0.9, 9: 0.4, 0: 0.5, 4: 0.5, 6: 0.3}.items():
        profile[pc] = weight
    return AudioFeatures(
        top_midi=71, ranking=[(71, 150), (67, 400)], top_times=[12.3], chroma_windows=[profile] * 3
    )


def test_dois_passarinhos_report():
    report = build_report(_g_major_features(), ceiling_midi=66)
    assert report.shift == -5
    assert report.alternative_shift == 7
    assert [(s.start, s.tonic, s.mode, s.new_key) for s in report.sections] == [
        (0.0, "G", "maior", "D maior")
    ]
    assert report.new_key == "D maior"
    assert report.scale_degree == "3ª"
    assert report.top_note.name == "B4"
    assert report.new_top_note.name == "F#4"
    assert report.ceiling.name == "F#4"
    assert report.top_times == [12.3]
    assert report.ranking[0].note.name == "B4" and report.ranking[0].frames == 150


def test_modulating_song_lists_each_key_with_its_new_key():
    e_major = [0.05] * 12
    for pc, weight in {4: 1.0, 6: 0.5, 8: 0.8, 9: 0.3, 11: 0.9, 1: 0.5, 3: 0.5}.items():
        e_major[pc] = weight
    f_sharp_major = e_major[-2:] + e_major[:-2]  # sobe um tom inteiro
    features = AudioFeatures(
        top_midi=71,
        ranking=[(71, 150)],
        top_times=[1.0],
        chroma_windows=[e_major] * 4 + [f_sharp_major] * 4,
    )
    report = build_report(features, ceiling_midi=66)
    assert [(s.start, s.tonic, s.new_key) for s in report.sections] == [
        (0.0, "E", "B maior"),
        (40.0, "F#", "C# maior"),
    ]
    assert report.new_key == "B maior"  # o do primeiro trecho


def test_alternative_is_the_octave_up_when_shift_goes_down():
    # A#4 com teto C#4: principal -9 (C#4); alternativa +3 (C#5).
    features = AudioFeatures(
        top_midi=70, ranking=[(70, 150)], top_times=[1.0], chroma_windows=[[0.05] * 12]
    )
    report = build_report(features, ceiling_midi=61)
    assert (report.shift, report.alternative_shift) == (-9, 3)
    assert report.new_top_note.name == "C#4"
