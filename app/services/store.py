"""Armazenamento das análises em SQLite (SQLAlchemy assíncrono)."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import JSON, select
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.pitch import ALGO_VERSION, AudioFeatures


class Base(DeclarativeBase):
    """Base declarativa das tabelas."""


class Analysis(Base):
    """Features puras de uma música, independentes do teto, chaveadas pelo id do vídeo."""

    __tablename__ = "analyses"

    video_id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str]
    duration_seconds: Mapped[int]
    top_midi: Mapped[int]
    ranking: Mapped[list[list[int]]] = mapped_column(JSON)
    top_times: Mapped[list[float]] = mapped_column(JSON)
    chroma_profile: Mapped[list[float]] = mapped_column(JSON)
    algo_version: Mapped[int]
    created_at: Mapped[datetime]  # UTC; o SQLite devolve sem fuso


_engine: AsyncEngine | None = None
_sessions: async_sessionmaker[AsyncSession] | None = None


def configure(database_path: Path) -> None:
    """Aponta o armazenamento para o arquivo informado, criando a pasta se faltar."""
    global _engine, _sessions
    database_path.parent.mkdir(parents=True, exist_ok=True)
    _engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    _sessions = async_sessionmaker(_engine, expire_on_commit=False)


async def create_tables() -> None:
    """Cria as tabelas que ainda não existem."""
    assert _engine is not None, "store.configure() não foi chamado"
    async with _engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)


async def dispose() -> None:
    """Fecha as conexões do banco."""
    if _engine is not None:
        await _engine.dispose()


def session() -> AsyncSession:
    """Uma sessão nova, para usar com `async with`."""
    assert _sessions is not None, "store.configure() não foi chamado"
    return _sessions()


async def get_session() -> AsyncIterator[AsyncSession]:
    """Dependência do FastAPI: uma sessão por requisição."""
    async with session() as current:
        yield current


async def find(session: AsyncSession, video_id: str) -> Analysis | None:
    """Busca a análise guardada de um vídeo."""
    return await session.get(Analysis, video_id)


async def save(
    session: AsyncSession,
    video_id: str,
    title: str,
    duration_seconds: int,
    features: AudioFeatures,
) -> Analysis:
    """Grava a análise do vídeo, sobrescrevendo a anterior se houver."""
    row = Analysis(
        video_id=video_id,
        title=title,
        duration_seconds=duration_seconds,
        top_midi=features.top_midi,
        ranking=[list(pair) for pair in features.ranking],
        top_times=features.top_times,
        chroma_profile=features.chroma_profile,
        algo_version=ALGO_VERSION,
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    row = await session.merge(row)
    await session.commit()
    return row


async def list_recent(session: AsyncSession) -> list[Analysis]:
    """Todas as análises, das mais recentes para as mais antigas."""
    result = await session.scalars(select(Analysis).order_by(Analysis.created_at.desc()))
    return list(result)


def to_features(row: Analysis) -> AudioFeatures:
    """Reconstrói as features guardadas para montar um relatório."""
    return AudioFeatures(
        top_midi=row.top_midi,
        ranking=[(midi, frames) for midi, frames in row.ranking],
        top_times=row.top_times,
        chroma_profile=row.chroma_profile,
    )
