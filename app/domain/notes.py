"""Nomes de notas e as duas numerações de oitava (padrão e do usuário)."""

from dataclasses import dataclass

NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Teto padrão: F#3 na numeração do usuário (F#4 no padrão).
DEFAULT_CEILING_MIDI = 66

# Faixa da lista de teto: C2 a C4 na numeração do usuário.
_CEILING_MIN_MIDI = 48
_CEILING_MAX_MIDI = 72


@dataclass(frozen=True)
class CeilingOption:
    """Uma opção da lista de teto, com a nota nas duas numerações."""

    midi: int
    user: str
    standard: str


def pitch_class_name(pc: int) -> str:
    """Nome da nota (sem oitava) para uma classe de altura de 0 a 11."""
    return NOTE_NAMES[pc % 12]


def standard_label(midi: int) -> str:
    """Nota com oitava na numeração padrão (dó central = C4)."""
    return f"{pitch_class_name(midi)}{midi // 12 - 1}"


def user_label(midi: int) -> str:
    """Nota com oitava na numeração do usuário (uma oitava abaixo da padrão)."""
    return f"{pitch_class_name(midi)}{midi // 12 - 2}"


def ceiling_options() -> list[CeilingOption]:
    """Opções de teto em ordem crescente, da mais grave à mais aguda."""
    return [
        CeilingOption(midi, user_label(midi), standard_label(midi))
        for midi in range(_CEILING_MIN_MIDI, _CEILING_MAX_MIDI + 1)
    ]
