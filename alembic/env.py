"""Alembic 환경 설정"""
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
from src.adapters.persistence.models import Base
target_metadata = Base.metadata

# Alembic에서 사용할 때는 환경변수에서 설정을 읽지 않도록 설정
import os
os.environ.pop('api_prefix', None)
os.environ.pop('debug', None)
os.environ.pop('sync_batch_size', None)
os.environ.pop('sync_max_workers', None)
os.environ.pop('sync_retry_attempts', None)
os.environ.pop('sync_timeout_seconds', None)
os.environ.pop('max_shipping_days', None)
os.environ.pop('coupang_api_timeout', None)
os.environ.pop('coupang_rate_limit_per_minute', None)
os.environ.pop('log_file_path', None)
os.environ.pop('secret_key', None)

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # SQLite의 경우 동기 엔진 사용
    from src.adapters.persistence.models import sync_engine
    connectable = sync_engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
