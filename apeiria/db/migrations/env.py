"""Alembic migration environment configuration."""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from apeiria.db.base import Base
from apeiria.db.models import *  # noqa: F403

target_metadata = Base.metadata


def _resolve_url() -> str:
    override = context.config.get_main_option("sqlalchemy.url")
    if override and override != "sqlite:///data/db/apeiria.sqlite3":
        return override
    from apeiria.db.runtime import database_runtime

    return f"sqlite:///{database_runtime.database_path()}"


def run_migrations_offline() -> None:
    url = _resolve_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = _resolve_url()
    connectable = create_engine(url)
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()


config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
