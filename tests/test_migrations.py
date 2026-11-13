import asyncio
import os

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from app.services import migrate, store

URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://postgres:dev@localhost:5432/tonalidade_test"
)


async def test_upgrade_creates_all_tables():
    """A migração inicial sobe do zero com todas as tabelas e e-mail único."""
    engine = create_async_engine(URL)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{store.SCHEMA}" CASCADE'))
        await asyncio.to_thread(migrate.upgrade_head, URL)
        async with engine.begin() as connection:
            rows = await connection.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = :s"),
                {"s": store.SCHEMA},
            )
            assert {row[0] for row in rows} == {
                "analyses",
                "jobs",
                "users",
                "auth_tokens",
                "user_settings",
                "user_analyses",
                "alembic_version",
            }
            columns = await connection.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = :s AND table_name = 'analyses'"
                ),
                {"s": store.SCHEMA},
            )
            assert "top_chords" in {row[0] for row in columns}
            insert = text(
                "INSERT INTO tonalidade.users (id, name, email, password_hash, created_at) "
                "VALUES (gen_random_uuid(), 'a', 'a@x.com', 'h', now())"
            )
            await connection.execute(insert)
        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(insert)
    finally:
        await engine.dispose()
