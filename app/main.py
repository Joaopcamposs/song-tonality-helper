"""Aplicação FastAPI: expõe a API em /api e serve o front estático."""

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.domain import security
from app.routers import analyses, auth
from app.services import migrate, store


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    """Migra e abre o banco na subida (`DATABASE_URL`) e fecha as conexões ao desligar."""
    security.secret_key()  # falha cedo se `SECRET_KEY` não estiver definida
    url = store.database_url()
    # O Alembic usa o próprio loop; numa thread ele não briga com o da API.
    await asyncio.to_thread(migrate.upgrade_head, url)
    store.configure(url)
    yield
    await store.dispose()


app = FastAPI(
    lifespan=lifespan,
    title="Tonalidade",
    description="Descobre o tom ideal de uma música do YouTube para o seu tom teto.",
)

app.include_router(auth.router)
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
