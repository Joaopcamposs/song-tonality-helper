"""Aplica as migrações do Alembic no banco (`alembic upgrade head`)."""

from pathlib import Path

from alembic.config import Config

from alembic import command

ROOT = Path(__file__).parent.parent.parent


def upgrade_head(url: str) -> None:
    """Leva o banco da URL até a última migração; bloqueante, rode em outra thread."""
    config = Config(str(ROOT / "alembic.ini"))
    # O configparser trata `%` como interpolação; a URL pode conter senha codificada.
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    command.upgrade(config, "head")
