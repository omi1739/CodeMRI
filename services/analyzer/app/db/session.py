from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.db.models import Base


def _sqlite_url(url: str) -> str:
    if url.startswith("sqlite:///"):
        raw = url[len("sqlite:///") :]
        if raw and not raw.startswith("/") and ":" not in raw.split("/")[0]:
            path = settings.db_path
            return f"sqlite:///{path.as_posix()}"
    return url


engine = create_engine(
    _sqlite_url(settings.database_url),
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)

if engine.dialect.name == "sqlite":

    @event.listens_for(engine, "connect")
    def _sqlite_pragma(dbapi_conn, _record):  # type: ignore[no-untyped-def]
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)
    recover_interrupted_scans()


def recover_interrupted_scans() -> None:
    """Background tasks do not survive restarts: mark non-terminal scans as failed."""
    from sqlalchemy import update

    from app.db.models import Scan

    with engine.begin() as conn:
        conn.execute(
            update(Scan)
            .where(Scan.status.notin_(("completed", "failed")))
            .values(
                status="failed",
                current_stage="failed",
                error_message="Scan interrupted by server restart.",
            )
        )


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
