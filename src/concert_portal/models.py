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


class TicketBase(SQLModel):
    concert_id: int = Field(foreign_key="concert.id")
    category: str  # US15 — e.g. "VIP", "Standard"
    price: float  # US16
    quantity: int  # US17 — total tickets available


class Ticket(TicketBase, table=True):
    """Database table."""

    id: int | None = Field(default=None, primary_key=True)
    sold: int = Field(default=0)  # used by US19 to prevent overselling


class TicketCreate(TicketBase):
    """What the organiser sends."""


class TicketRead(TicketBase):
    """What the API returns."""

    id: int
    sold: int
