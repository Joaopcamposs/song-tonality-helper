from app.domain.notes import DEFAULT_CEILING_MIDI, ceiling_options, note_label


def test_note_label_uses_middle_c_as_c4():
    assert note_label(60) == "C4"
    assert note_label(71) == "B4"


def test_ceiling_options_range():
    options = ceiling_options()
    assert len(options) == 25
    assert options[0].name == "C3"
    assert options[-1].name == "C5"
    default = next(o for o in options if o.midi == DEFAULT_CEILING_MIDI)
    assert default.name == "F#4"
