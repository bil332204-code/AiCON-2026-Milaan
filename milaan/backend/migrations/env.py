from alembic import context
from sqlalchemy import pool, create_engine
from app.config import Settings
from app.models import Base
from app.database import database_url
from pathlib import Path

settings = Settings()
url = database_url(settings.migration_database_url or settings.database_url)
if url.get_backend_name() == "postgresql" and not settings.migration_database_url and url.host and "-pooler." in url.host:
    raise ValueError("Set MIGRATION_DATABASE_URL to the direct PostgreSQL endpoint")
if url.get_backend_name() == "sqlite" and url.database and url.database != ":memory:":
    Path(url.database).parent.mkdir(parents=True, exist_ok=True)

def run_migrations_offline():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"}, compare_type=True)
    with context.begin_transaction(): context.run_migrations()

def run_migrations_online():
    engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True,
                           **({"connect_args": {"prepare_threshold": None, "connect_timeout": 10}} if url.get_backend_name() == "postgresql" else {}))
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True,
                          render_as_batch=connection.dialect.name == "sqlite")
        with context.begin_transaction(): context.run_migrations()
    engine.dispose()

run_migrations_offline() if context.is_offline_mode() else run_migrations_online()
