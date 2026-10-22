"""Jobs de análise em memória: baixa o áudio, analisa e guarda o relatório."""

import logging
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.domain.errors import DomainError
from app.domain.pitch import analyze_audio
from app.domain.schemas import Report
from app.services.report import build_report
from app.services.youtube import download_audio

logger = logging.getLogger(__name__)

MAX_JOBS = 50


@dataclass
class Job:
    """Estado de uma análise em andamento ou concluída."""

    id: str
    status: Literal["downloading", "analyzing", "done", "error"] = "downloading"
    error: str | None = None
    report: Report | None = None


# Dicionário preserva a ordem de inserção: o primeiro item é o job mais antigo.
_jobs: dict[str, Job] = {}


def create() -> str:
    """Registra um job novo, descartando o mais antigo se passar do limite."""
    job_id = uuid.uuid4().hex
    _jobs[job_id] = Job(id=job_id)
    while len(_jobs) > MAX_JOBS:
        del _jobs[next(iter(_jobs))]
    return job_id


def get(job_id: str) -> Job | None:
    """Busca um job pelo id."""
    return _jobs.get(job_id)


def run(job_id: str, url: str, ceiling_midi: int) -> None:
    """Executa o job: sempre termina em `done` ou `error` e apaga o áudio temporário."""
    job = _jobs.get(job_id)
    if job is None:
        return
    try:
        with tempfile.TemporaryDirectory() as tmp:
            path: Path = download_audio(url, Path(tmp))
            job.status = "analyzing"
            features = analyze_audio(path)
        job.report = build_report(features, ceiling_midi)
        job.status = "done"
    except DomainError as error:
        job.status, job.error = "error", error.message
    except Exception:
        logger.exception("Falha inesperada na análise %s", job_id)
        job.status, job.error = "error", "Erro inesperado ao analisar a música."
