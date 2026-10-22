"""Aplicação FastAPI: expõe a API em /api e serve o front estático."""

from fastapi import FastAPI

from app.routers import analyses

app = FastAPI(
    title="Song Tonality Helper",
    description="Descobre o tom ideal de uma música do YouTube para o seu tom teto.",
)

app.include_router(analyses.router)


@app.get(
    "/api/health",
    tags=["health"],
    summary="Verifica se a API está no ar",
    description="Devolve `ok` quando o servidor está respondendo.",
)
def health() -> dict[str, str]:
    """Resposta fixa usada para checar que o servidor subiu."""
    return {"status": "ok"}
