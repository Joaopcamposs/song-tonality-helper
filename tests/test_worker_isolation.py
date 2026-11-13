"""A análise de áudio roda num processo filho, para a memória do pico voltar ao sistema."""

import os

import pytest

from app import worker
from app.domain import pitch
from app.domain.errors import NoMelodyError


def _pid_of_caller(_: int) -> int:
    """Pid do processo que executa a função."""
    return os.getpid()


def test_isolated_runs_in_another_process():
    assert worker._isolated(_pid_of_caller, 0) != os.getpid()


def test_worker_analysis_matches_the_in_process_one(make_wav):
    wav = make_wav([(67, 10), (71, 10)])
    isolated = worker.analyze_audio(wav)
    direct = pitch.analyze_audio(wav)
    assert (isolated.top_midi, isolated.top_times, isolated.top_chords) == (
        direct.top_midi,
        direct.top_times,
        direct.top_chords,
    )


def test_domain_error_crosses_the_process_boundary(make_wav):
    with pytest.raises(NoMelodyError):
        worker.analyze_audio(make_wav([(None, 5)]))
