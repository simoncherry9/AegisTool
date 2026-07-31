"""Configuración de Alembic para AegisWiFi.

La URL de la BD se toma de ``aegiswifi.core.config.get_settings().database_url``
(minuta §9.1 SQLite por defecto, PostgreSQL opcional). Los metadatos objetivo son
``aegiswifi.database.base.Base.metadata``.
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Importable gracias a `prepend_sys_path = backend` en alembic.ini.
from aegiswifi.core.config import get_settings  # noqa: E402,F401
from aegiswifi.database.base import Base  # noqa: E402
from aegiswifi.database import models  # noqa: E402,F401 — registra modelos en el metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# URL resuelta desde la configuración de la aplicación (no desde alembic.ini).
config.set_main_option("sqlalchemy.url", get_settings().database_url)


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=True,  # mejor soporte para ALTER en SQLite
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
