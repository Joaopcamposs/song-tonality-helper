"""Ambiente do Alembic (async, schema `tonalidade`): a URL vem de `migrate` ou de `DATABASE_URL`."""

import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlalchemy.schema import CreateSchema

from alembic import context
from app.services.store import SCHEMA, Base, database_url

config = context.config
if not config.get_main_option("sqlalchemy.url"):
    # O configparser trata `%` como interpolação; a URL pode conter senha codificada.
    config.set_main_option("sqlalchemy.url", database_url().replace("%", "%%"))

# Não deixa o Alembic desligar os loggers do app quando roda dentro da API.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def include_name(name: str | None, type_: str, parent_names: dict[str, str | None]) -> bool:
    """No autogenerate, só enxerga o schema do app (o banco é compartilhado com outros)."""
    if type_ == "schema":
        return name == SCHEMA
    return True


def run_migrations_offline() -> None:
    """Gera o SQL sem conectar ao banco."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        version_table_schema=SCHEMA,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Executa as migrações na conexão recebida."""
    # O schema (e com ele a tabela de versões) precisa existir antes da primeira migração.
    connection.execute(CreateSchema(SCHEMA, if_not_exists=True))
    connection.commit()
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema=SCHEMA,
        include_schemas=True,
        include_name=include_name,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Abre uma conexão async (sem pool) e roda as migrações nela."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_async_migrations())
