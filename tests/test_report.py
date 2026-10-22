from app.domain.pitch import AudioFeatures
from app.services.report import build_report


def _g_major_features() -> AudioFeatures:
    profile = [0.05] * 12
    for pc, weight in {7: 1.0, 11: 0.8, 2: 0.9, 9: 0.4, 0: 0.5, 4: 0.5, 6: 0.3}.items():
        profile[pc] = weight
    return AudioFeatures(
        top_midi=71, ranking=[(71, 150), (67, 400)], top_times=[12.3], chroma_profile=profile
    )


def test_dois_passarinhos_report():
    report = build_report(_g_major_features(), ceiling_midi=66)
    assert report.shift == -5
    assert report.alternative_shift == 7
    assert report.keys[0].tonic == "G" and report.keys[0].mode == "maior"
    assert report.new_key == "D maior"
    assert report.scale_degree == "3ª"
    assert (report.top_note.user, report.top_note.standard) == ("B3", "B4")
    assert report.new_top_note.user == "F#3"
    assert report.ceiling.user == "F#3"
    assert report.top_times == [12.3]
    assert report.ranking[0].note.user == "B3" and report.ranking[0].frames == 150
