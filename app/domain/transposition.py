"""Cálculo do deslocamento em semitons, do novo tom e do grau da nota na escala."""

_DEGREES = ["tônica", "♭2ª", "2ª", "♭3ª", "3ª", "4ª", "♭5ª", "5ª", "♭6ª", "6ª", "♭7ª", "7ª"]


def shift_semitones(top_midi: int, ceiling_midi: int) -> int:
    """Menor deslocamento (de -6 a +5) que leva a nota mais aguda ao teto, módulo oitava."""
    shift = (ceiling_midi - top_midi) % 12
    return shift - 12 if shift >= 6 else shift


def transpose_tonic(tonic_pc: int, shift: int) -> int:
    """Classe de altura da tônica depois de aplicar o deslocamento."""
    return (tonic_pc + shift) % 12


def scale_degree(top_midi: int, tonic_pc: int) -> str:
    """Grau da nota em relação à tônica, em semitons acima dela."""
    return _DEGREES[(top_midi - tonic_pc) % 12]
