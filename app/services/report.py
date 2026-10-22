"""Monta o relatório final a partir das features do áudio e do teto escolhido."""

from app.domain.key import detect_key
from app.domain.notes import pitch_class_name, standard_label, user_label
from app.domain.pitch import AudioFeatures
from app.domain.schemas import KeyOut, NoteOut, RankedNote, Report
from app.domain.transposition import scale_degree, shift_semitones, transpose_tonic


def note_out(midi: int) -> NoteOut:
    """Nota nas duas numerações."""
    return NoteOut(midi=midi, user=user_label(midi), standard=standard_label(midi))


def build_report(features: AudioFeatures, ceiling_midi: int) -> Report:
    """Calcula o novo tom, o grau da nota e o resto do relatório."""
    candidates = detect_key(features.chroma_profile)
    best = candidates[0]
    shift = shift_semitones(features.top_midi, ceiling_midi)
    new_tonic = transpose_tonic(best.tonic_pc, shift)
    return Report(
        top_note=note_out(features.top_midi),
        ceiling=note_out(ceiling_midi),
        ranking=[
            RankedNote(note=note_out(midi), frames=frames) for midi, frames in features.ranking
        ],
        top_times=features.top_times,
        keys=[
            KeyOut(tonic=pitch_class_name(c.tonic_pc), mode=c.mode, score=round(c.score, 3))
            for c in candidates
        ],
        shift=shift,
        alternative_shift=shift + 12 if shift < 0 else shift - 12,
        new_key=f"{pitch_class_name(new_tonic)} {best.mode}",
        scale_degree=scale_degree(features.top_midi, best.tonic_pc),
        new_top_note=note_out(features.top_midi + shift),
    )
