from alembic import context
from sqlalchemy import pool, create_engine
from app.config import Settings
from app.models import Base
from pathlib import Path

url = Settings().database_url
if url.startswith("sqlite:///" ):
    Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)

def run_migrations_offline():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"}, compare_type=True)
    with context.begin_transaction(): context.run_migrations()

def run_migrations_online():
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True,
                          render_as_batch=connection.dialect.name == "sqlite")
        with context.begin_transaction(): context.run_migrations()
    engine.dispose()

run_migrations_offline() if context.is_offline_mode() else run_migrations_online()
