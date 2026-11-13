"""Cálculo do deslocamento em semitons, do novo tom e do grau da nota na escala."""

_DEGREES = ["tônica", "♭2º", "2º", "♭3º", "3º", "4º", "♭5º", "5º", "♭6º", "6º", "♭7º", "7º"]


def shift_semitones(top_midi: int, ceiling_midi: int) -> int:
    """Deslocamento (de -11 a 0) que leva a nota mais aguda ao teto sem passá-lo, módulo oitava."""
    return -((top_midi - ceiling_midi) % 12)


def transpose_tonic(tonic_pc: int, shift: int) -> int:
    """Classe de altura da tônica depois de aplicar o deslocamento."""
    return (tonic_pc + shift) % 12


def scale_degree(top_midi: int, tonic_pc: int) -> str:
    """Grau da nota em relação à tônica, em semitons acima dela."""
    return _DEGREES[(top_midi - tonic_pc) % 12]
