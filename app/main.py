"""Aplicação FastAPI: expõe a API em /api e serve o front estático."""

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.routers import analyses
from app.services import store


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Abre o banco na subida (`DATABASE_PATH`) e fecha as conexões ao desligar."""
    store.configure(Path(os.environ.get("DATABASE_PATH", "data/analyses.db")))
    await store.create_tables()
    yield
    await store.dispose()


app = FastAPI(
    lifespan=lifespan,
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


# O front estático vai por último para não esconder as rotas de /api.
app.mount("/", StaticFiles(directory=Path(__file__).parent.parent / "frontend", html=True))
