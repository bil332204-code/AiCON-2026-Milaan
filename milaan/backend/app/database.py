from pathlib import Path
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

def database_url(value):
    """Use psycopg 3 for provider postgres:// and postgresql:// URLs."""
    url = make_url(value)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    if url.drivername not in {"sqlite", "postgresql+psycopg"}:
        raise ValueError("Use SQLite or PostgreSQL with psycopg")
    return url


class Database:
    def __init__(self, url, *, pool_size=5, max_overflow=0, pool_timeout=10):
        url = database_url(url)
        self.sqlite = url.get_backend_name() == "sqlite"
        if self.sqlite and url.database and url.database != ":memory:":
            Path(url.database).parent.mkdir(parents=True, exist_ok=True)
        kw = {"connect_args": {"check_same_thread": False, "timeout": 30}} if self.sqlite else {
            "pool_pre_ping": True, "pool_size": pool_size, "max_overflow": max_overflow,
            "pool_timeout": pool_timeout, "pool_recycle": 300,
            # PgBouncer transaction pooling cannot retain session prepared statements.
            "connect_args": {"prepare_threshold": None, "connect_timeout": 10},
            "hide_parameters": True,
        }
        self.engine = create_engine(url, **kw)
        if self.sqlite:
            @event.listens_for(self.engine, "connect")
            def configure(connection, _):
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("PRAGMA busy_timeout=30000")
                connection.execute("PRAGMA journal_mode=WAL")
        else:
            @event.listens_for(self.engine, "begin")
            def bound_transaction(connection):
                # SET LOCAL is safe with transaction-mode poolers; no session state.
                connection.exec_driver_sql("SET LOCAL statement_timeout = '30s'")
                connection.exec_driver_sql("SET LOCAL lock_timeout = '10s'")
                connection.exec_driver_sql("SET LOCAL idle_in_transaction_session_timeout = '60s'")
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def begin(self, session):
        if self.sqlite:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")

    @contextmanager
    def transaction(self):
        with self.sessions() as session:
            try:
                self.begin(session)
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
