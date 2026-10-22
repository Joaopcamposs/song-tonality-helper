"""Rotas de análise: lista de tetos, criação de job e consulta do resultado."""

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.domain.errors import InvalidUrlError
from app.domain.notes import DEFAULT_CEILING_MIDI, ceiling_options
from app.domain.schemas import AnalysisRequest, CeilingOut, CeilingsOut, JobCreated, JobOut
from app.services import jobs
from app.services.youtube import validate_url

router = APIRouter(prefix="/api", tags=["analyses"])


@router.get(
    "/ceilings",
    summary="Lista os tetos disponíveis",
    description="Opções de tom teto (C2 a C4 na numeração do usuário) e a escolha padrão.",
)
def list_ceilings() -> CeilingsOut:
    """Opções da lista de teto, com as duas numerações."""
    options = [CeilingOut(midi=o.midi, user=o.user, standard=o.standard) for o in ceiling_options()]
    return CeilingsOut(options=options, default_midi=DEFAULT_CEILING_MIDI)


@router.post(
    "/analyses",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Inicia a análise de uma música",
    description="Recebe o link do YouTube e o teto; devolve o id do job para consulta.",
)
def create_analysis(body: AnalysisRequest, background: BackgroundTasks) -> JobCreated:
    """Valida o link, cria o job e agenda o processamento em segundo plano."""
    try:
        url = validate_url(body.url)
    except InvalidUrlError as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, error.message) from error
    job_id = jobs.create()
    background.add_task(jobs.run, job_id, url, body.ceiling_midi)
    return JobCreated(id=job_id)


@router.get(
    "/analyses/{job_id}",
    summary="Consulta o resultado de uma análise",
    description="Devolve o status (baixando, analisando, pronto ou erro) e o relatório pronto.",
)
def get_analysis(job_id: str) -> JobOut:
    """Estado atual do job; 404 se o id não existe."""
    job = jobs.get(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Análise não encontrada.")
    return JobOut(id=job.id, status=job.status, error=job.error, report=job.report)
