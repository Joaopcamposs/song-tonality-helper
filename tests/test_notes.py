from app.domain.notes import DEFAULT_CEILING_MIDI, ceiling_options, standard_label, user_label


def test_user_label_is_one_octave_below_standard():
    assert standard_label(71) == "B4"
    assert user_label(71) == "B3"


def test_ceiling_options_range():
    options = ceiling_options()
    assert len(options) == 25
    assert options[0].user == "C2"
    assert options[-1].user == "C4"
    default = next(o for o in options if o.midi == DEFAULT_CEILING_MIDI)
    assert (default.user, default.standard) == ("F#3", "F#4")
