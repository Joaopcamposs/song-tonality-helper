"""Armazenamento das análises no Postgres (SQLAlchemy assíncrono)."""

import os
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import JSON, ForeignKey, MetaData, String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.errors import DomainError
from app.domain.features import ALGO_VERSION, AudioFeatures
from app.domain.notes import DEFAULT_CEILING_MIDI

# Schema próprio no Postgres, para dividir o banco com outros apps.
SCHEMA = "tonalidade"


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
    chroma_windows: Mapped[list[list[float]]] = mapped_column(JSON)
    top_chords: Mapped[list[str | None]] = mapped_column(JSON, server_default="[]")
    algo_version: Mapped[int]
    created_at: Mapped[datetime]  # UTC ingênuo (coluna sem fuso)


JobStatus = Literal["pending", "downloading", "analyzing", "error"]


class Job(Base):
    """Andamento de uma análise em curso ou que falhou, chaveado pelo id do vídeo."""

    __tablename__ = "jobs"

    video_id: Mapped[str] = mapped_column(primary_key=True)
    status: Mapped[JobStatus] = mapped_column(String)
    error: Mapped[str | None]
    updated_at: Mapped[datetime]  # UTC ingênuo, como em Analysis


class User(Base):
    """Conta de uma pessoa (mesmas colunas da tabela `users` do repertorio)."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str]
    email: Mapped[str] = mapped_column(unique=True)  # sempre em minúsculas
    password_hash: Mapped[str]
    created_at: Mapped[datetime]  # UTC ingênuo, como em Analysis
    email_verified_at: Mapped[datetime | None]


class AuthToken(Base):
    """Token de uso único para confirmar o e-mail (`verify`) ou redefinir a senha (`reset`)."""

    __tablename__ = "auth_tokens"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String)
    token_hash: Mapped[str] = mapped_column(index=True)  # só o hash é guardado
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]
    created_at: Mapped[datetime]


class UserSettings(Base):
    """Preferências de uma pessoa; sem linha vale o teto padrão."""

    __tablename__ = "user_settings"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"), primary_key=True
    )
    ceiling_midi: Mapped[int]


class UserAnalysis(Base):
    """Liga uma pessoa às músicas que ela pediu (as features são compartilhadas)."""

    __tablename__ = "user_analyses"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(f"{SCHEMA}.users.id", ondelete="CASCADE"), primary_key=True
    )
    video_id: Mapped[str] = mapped_column(primary_key=True)
    created_at: Mapped[datetime]


_engine: AsyncEngine | None = None
_sessions: async_sessionmaker[AsyncSession] | None = None


def database_url() -> str:
    """Lê `DATABASE_URL` do ambiente; sem ela o app não sobe."""
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise DomainError(
            "Defina DATABASE_URL com a URL do Postgres "
            "(postgresql+asyncpg://usuario:senha@host:5432/banco); "
            "localmente, rode `make db` e use `make run`."
        )
    return url


def configure(url: str) -> None:
    """Aponta o armazenamento para o Postgres da URL (`postgresql+asyncpg://...`)."""
    global _engine, _sessions
    _engine = create_async_engine(url)
    _sessions = async_sessionmaker(_engine, expire_on_commit=False)


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
        chroma_windows=features.chroma_windows,
        top_chords=features.top_chords,
        algo_version=ALGO_VERSION,
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    row = await session.merge(row)
    await session.commit()
    return row


def to_features(row: Analysis) -> AudioFeatures:
    """Reconstrói as features guardadas para montar um relatório."""
    return AudioFeatures(
        top_midi=row.top_midi,
        ranking=[(midi, frames) for midi, frames in row.ranking],
        top_times=row.top_times,
        chroma_windows=row.chroma_windows,
        top_chords=row.top_chords,
    )


def _now() -> datetime:
    """Agora em UTC ingênuo, como as colunas de data."""
    return datetime.now(UTC).replace(tzinfo=None)


async def link(session: AsyncSession, user_id: UUID, video_id: str) -> None:
    """Põe a música na lista da pessoa; sem efeito se ela já estava lá."""
    if await is_linked(session, user_id, video_id):
        return
    session.add(UserAnalysis(user_id=user_id, video_id=video_id, created_at=_now()))
    try:
        await session.commit()
    except IntegrityError:  # dois pedidos simultâneos da mesma pessoa
        await session.rollback()


async def unlink(session: AsyncSession, user_id: UUID, video_id: str) -> bool:
    """Tira a música da lista da pessoa (as features ficam); False se ela não estava lá."""
    row = await session.get(UserAnalysis, (user_id, video_id))
    if row is None:
        return False
    await session.delete(row)
    await session.commit()
    return True


async def is_linked(session: AsyncSession, user_id: UUID, video_id: str) -> bool:
    """Diz se a música está na lista da pessoa."""
    return await session.get(UserAnalysis, (user_id, video_id)) is not None


async def has_links(session: AsyncSession, video_id: str) -> bool:
    """Diz se alguém ainda tem a música na lista."""
    found = await session.scalar(
        select(UserAnalysis.video_id).where(UserAnalysis.video_id == video_id)
    )
    return found is not None


async def list_for_user(session: AsyncSession, user_id: UUID) -> list[Analysis]:
    """Análises prontas da lista da pessoa, das mais recentemente pedidas para as mais antigas."""
    result = await session.scalars(
        select(Analysis)
        .join(UserAnalysis, UserAnalysis.video_id == Analysis.video_id)
        .where(UserAnalysis.user_id == user_id)
        .order_by(UserAnalysis.created_at.desc())
    )
    return list(result)


async def get_ceiling(session: AsyncSession, user_id: UUID) -> int:
    """Tom teto salvo da pessoa, ou o padrão se ela ainda não escolheu."""
    saved = await session.get(UserSettings, user_id)
    return DEFAULT_CEILING_MIDI if saved is None else saved.ceiling_midi


async def set_ceiling(session: AsyncSession, user_id: UUID, midi: int) -> None:
    """Guarda o tom teto da pessoa."""
    await session.merge(UserSettings(user_id=user_id, ceiling_midi=midi))
    await session.commit()
