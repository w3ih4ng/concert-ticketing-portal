from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = "sqlite:///concert_portal.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


def init_db() -> None:
    """Create tables if they don't exist yet."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency: one database session per request."""
    with Session(engine) as session:
        yield session
