"""Monta o relatório final a partir das features do áudio e do teto escolhido."""

from app.domain.features import AudioFeatures
from app.domain.key import key_sections
from app.domain.notes import note_label, pitch_class_name
from app.domain.schemas import KeySectionOut, NoteOut, RankedNote, Report
from app.domain.transposition import scale_degree, shift_semitones, transpose_tonic


def note_out(midi: int) -> NoteOut:
    """Nota com nome e oitava."""
    return NoteOut(midi=midi, name=note_label(midi))


def _new_key(tonic_pc: int, mode: str, shift: int) -> str:
    """Nome do tom (tônica e modo) depois de deslocar `shift` semitons."""
    return f"{pitch_class_name(transpose_tonic(tonic_pc, shift))} {mode}"


def build_report(features: AudioFeatures, ceiling_midi: int) -> Report:
    """Calcula o novo tom, o grau da nota e o resto do relatório."""
    sections = key_sections(features.chroma_windows)
    first = sections[0]
    shift = shift_semitones(features.top_midi, ceiling_midi)
    return Report(
        top_note=note_out(features.top_midi),
        ceiling=note_out(ceiling_midi),
        ranking=[
            RankedNote(note=note_out(midi), frames=frames) for midi, frames in features.ranking
        ],
        top_times=features.top_times,
        sections=[
            KeySectionOut(
                start=round(s.start, 1),
                tonic=pitch_class_name(s.tonic_pc),
                mode=s.mode,
                score=round(s.score, 3),
                new_key=_new_key(s.tonic_pc, s.mode, shift),
            )
            for s in sections
        ],
        shift=shift,
        alternative_shift=shift + 12 if shift < 0 else shift - 12,
        new_key=_new_key(first.tonic_pc, first.mode, shift),
        scale_degree=scale_degree(features.top_midi, first.tonic_pc),
        new_top_note=note_out(features.top_midi + shift),
    )
