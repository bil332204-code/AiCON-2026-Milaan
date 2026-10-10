from pathlib import Path
from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

class Database:
    def __init__(self, url):
        self.sqlite = url.startswith("sqlite")
        if self.sqlite and ":memory:" not in url:
            Path(url.split("///", 1)[1]).parent.mkdir(parents=True, exist_ok=True)
        kw = {"connect_args": {"check_same_thread": False, "timeout": 30}} if self.sqlite else {"pool_pre_ping": True}
        self.engine = create_engine(url, **kw)
        if self.sqlite:
            @event.listens_for(self.engine, "connect")
            def configure(connection, _):
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("PRAGMA busy_timeout=30000")
                connection.execute("PRAGMA journal_mode=WAL")
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
