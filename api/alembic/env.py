"""Alembic environment.

We don't use the SQLAlchemy ORM in InsightFinder -- the runtime app
uses raw asyncpg. Alembic is only here for migration management, and
all migrations are written as raw SQL via ``op.execute(...)``.

The DATABASE_URL comes from app.settings (which reads .env) so we have
exactly one source of truth for connection info. SQLAlchemy uses
psycopg as the sync driver; we explicitly switch to the
``postgresql+psycopg`` dialect so it doesn't try the legacy psycopg2.
"""

from __future__ import annotations

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.settings import settings


# Alembic Config object backed by alembic.ini.
config = context.config

# Inject the runtime DATABASE_URL, swapping the dialect so SQLAlchemy
# loads psycopg (v3) instead of the legacy psycopg2.
config.set_main_option(
    "sqlalchemy.url",
    settings.database_url.replace("postgresql://", "postgresql+psycopg://", 1),
)

# Standard logging config from alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# No ORM models -- migrations are raw SQL only.
target_metadata = None


def run_migrations_offline() -> None:
    """Generate SQL without connecting (rarely used; kept for completeness)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Connect to the DB and apply migrations."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
