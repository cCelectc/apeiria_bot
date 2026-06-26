import asyncio

import apeiria.db.models  # noqa: F401
from alembic import context
from apeiria.db.base import Base

config = context.config

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # noqa: ANN001
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    url = config.get_main_option("sqlalchemy.url")
    if url and ("aiosqlite" in url or "+async" in url):
        from sqlalchemy import pool
        from sqlalchemy.ext.asyncio import async_engine_from_config

        async def _async_upgrade():
            connectable = async_engine_from_config(
                config.get_section(config.config_ini_section, {}),
                prefix="sqlalchemy.",
                poolclass=pool.NullPool,
            )
            async with connectable.connect() as conn:
                await conn.run_sync(do_run_migrations)
            await connectable.dispose()

        asyncio.run(_async_upgrade())
    else:
        from sqlalchemy import engine_from_config

        connectable = engine_from_config(
            config.get_section(config.config_ini_section, {}),
            prefix="sqlalchemy.",
        )
        with connectable.connect() as conn:
            do_run_migrations(conn)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
