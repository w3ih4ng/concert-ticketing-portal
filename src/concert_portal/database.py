from collections.abc import Generator

from sqlalchemy import inspect, text
from sqlmodel import Session, SQLModel, create_engine

DATABASE_URL = "sqlite:///concert_portal.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


def migrate_booking_user_id() -> None:
    """Add the booking user reference to databases created before SCRUM-119."""

    inspector = inspect(engine)

    if "booking" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("booking")}

    with engine.begin() as connection:
        if "user_id" not in columns:
            connection.execute(
                text("ALTER TABLE booking " "ADD COLUMN user_id INTEGER " "REFERENCES user(id)")
            )

        connection.execute(
            text("CREATE INDEX IF NOT EXISTS " "ix_booking_user_id ON booking (user_id)")
        )


def init_db() -> None:
    """Create tables and apply lightweight compatibility migrations."""

    SQLModel.metadata.create_all(engine)
    migrate_booking_user_id()


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency: one database session per request."""

    with Session(engine) as session:
        yield session
