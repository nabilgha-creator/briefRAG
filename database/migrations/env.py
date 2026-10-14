"""Alembic : URL lue dans le .env (backend.database.db), schéma cible = backend.database.models.
alembic upgrade head | alembic revision --autogenerate -m "..." | alembic check"""
from logging.config import fileConfig

import pgvector.sqlalchemy  # noqa: F401  type vector utilisé par les migrations générées
from alembic import context
from sqlalchemy import create_engine, pool

from backend.database.db import DATABASE_URL
from backend.database.models import Base

config = context.config
if config.config_file_name is not None :
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None :
    """génère le SQL sans se connecter (alembic upgrade head --sql)"""
    context.configure(url=DATABASE_URL.render_as_string(hide_password=False), target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"}, compare_type=True)
    with context.begin_transaction() :
        context.run_migrations()


def run_migrations_online() -> None :
    connectable = create_engine(DATABASE_URL, poolclass=pool.NullPool)
    with connectable.connect() as connection :
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction() :
            context.run_migrations()


if context.is_offline_mode() :
    run_migrations_offline()
else :
    run_migrations_online()
