from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.infrastructure.database import Base
from app.infrastructure.repository import SQLAlchemySupportRepository  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", get_settings().database_url.replace("%", "%%"))
target_metadata = Base.metadata
LEGACY_TABLES = {
    "after_sale_tickets",
    "approval_tasks",
    "audit_logs",
    "chat_messages",
    "conversations",
    "logistics",
    "orders",
}


def include_object(object_, name: str | None, type_: str, reflected: bool, compare_to):
    if os.getenv("ALEMBIC_ONLY_LEGACY") != "true":
        return True
    table_name = (
        name if type_ == "table" else getattr(getattr(object_, "table", None), "name", None)
    )
    return table_name in LEGACY_TABLES


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        include_object=include_object,
        dialect_opts={"paramstyle": "named"},
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
            include_object=include_object,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
