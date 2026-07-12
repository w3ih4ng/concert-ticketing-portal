from sqlmodel import Field, SQLModel


class ConcertBase(SQLModel):
    title: str
    date: str
    venue: str
    organiser: str


class Concert(ConcertBase, table=True):
    """Database table."""

    id: int | None = Field(default=None, primary_key=True)


class ConcertCreate(ConcertBase):
    """What the organiser sends (no id yet)."""


class ConcertRead(ConcertBase):
    """What the API returns (id assigned by the database)."""

    id: int
