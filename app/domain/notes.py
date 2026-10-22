"""Nomes de notas com oitava na numeração padrão (dó central = C4)."""

from dataclasses import dataclass

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Teto padrão: F#4.
DEFAULT_CEILING_MIDI = 66

# Faixa da lista de teto: C3 a C5.
_CEILING_MIN_MIDI = 48
_CEILING_MAX_MIDI = 72


@dataclass(frozen=True)
class CeilingOption:
    """Uma opção da lista de teto."""

    midi: int
    name: str


def pitch_class_name(pc: int) -> str:
    """Nome da nota (sem oitava) para uma classe de altura de 0 a 11."""
    return NOTE_NAMES[pc % 12]


def note_label(midi: int) -> str:
    """Nota com oitava (dó central = C4 = 60)."""
    return f"{pitch_class_name(midi)}{midi // 12 - 1}"


def ceiling_options() -> list[CeilingOption]:
    """Opções de teto em ordem crescente, da mais grave à mais aguda."""
    return [
        CeilingOption(midi, note_label(midi))
        for midi in range(_CEILING_MIN_MIDI, _CEILING_MAX_MIDI + 1)
    ]
