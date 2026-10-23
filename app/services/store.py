"""Armazenamento das análises em SQLite ou Postgres (SQLAlchemy assíncrono)."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from sqlalchemy import JSON, MetaData, String, make_url, select, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.pitch import ALGO_VERSION, AudioFeatures

# Schema próprio no Postgres, para dividir o banco com outros apps; o SQLite não tem schema.
SCHEMA = "song-tonality-helper"


class Base(DeclarativeBase):
    """Base declarativa das tabelas, todas no schema `SCHEMA`."""

    metadata = MetaData(schema=SCHEMA)


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


JobStatus = Literal["pending", "downloading", "analyzing", "error"]


class Job(Base):
    """Andamento de uma análise em curso ou que falhou, chaveado pelo id do vídeo."""

    __tablename__ = "jobs"

    video_id: Mapped[str] = mapped_column(primary_key=True)
    status: Mapped[JobStatus] = mapped_column(String)
    error: Mapped[str | None]
    updated_at: Mapped[datetime]  # UTC ingênuo, como em Analysis


_engine: AsyncEngine | None = None
_sessions: async_sessionmaker[AsyncSession] | None = None


def configure(url: str) -> None:
    """Aponta o armazenamento para a URL (SQLite ou Postgres); no SQLite cria a pasta se faltar."""
    global _engine, _sessions
    parsed = make_url(url)
    if parsed.get_backend_name() == "sqlite" and parsed.database:
        Path(parsed.database).parent.mkdir(parents=True, exist_ok=True)
    options = (
        {"schema_translate_map": {SCHEMA: None}} if parsed.get_backend_name() == "sqlite" else {}
    )
    _engine = create_async_engine(url, execution_options=options)
    _sessions = async_sessionmaker(_engine, expire_on_commit=False)


async def create_tables() -> None:
    """Cria o schema (só no Postgres) e as tabelas que ainda não existem."""
    assert _engine is not None, "store.configure() não foi chamado"
    async with _engine.begin() as connection:
        if connection.dialect.name == "postgresql":
            await connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{SCHEMA}"'))
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


async def remove(session: AsyncSession, video_id: str) -> bool:
    """Apaga a análise do vídeo; devolve False se não havia registro."""
    row = await session.get(Analysis, video_id)
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True


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
