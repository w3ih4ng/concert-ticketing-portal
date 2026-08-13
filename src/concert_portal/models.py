from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class UserBase(SQLModel):
    """Fields shared by stored users and API responses."""

    name: str
    email: str
    phone: str
    role: str


class User(UserBase, table=True):
    """Registered portal user."""

    id: int | None = Field(default=None, primary_key=True)
    password_hash: str
    email: str = Field(index=True, unique=True)


class AttendeeCreate(SQLModel):
    """Data required to register an attendee."""

    name: str
    email: str
    phone: str
    password: str


class UserRead(UserBase):
    """Safe user information returned by the API."""

    id: int


class LoginRequest(SQLModel):
    """Credentials submitted through the login API."""

    email: str
    password: str


class LoginResponse(UserRead):
    """Safe information returned after successful login."""

    redirect_url: str


class OrganiserProfile(SQLModel, table=True):
    """Organisation details submitted by an organiser."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(
        foreign_key="user.id",
        index=True,
        unique=True,
    )
    organisation_name: str
    registration_number: str
    organisation_address: str
    status: str = "pending"


class OrganiserCreate(SQLModel):
    """Data required to submit an organiser-registration request."""

    name: str
    email: str
    phone: str
    password: str
    organisation_name: str
    registration_number: str
    organisation_address: str


class OrganiserRead(SQLModel):
    """Safe organiser-registration information returned by the API."""

    id: int
    user_id: int
    name: str
    email: str
    phone: str
    role: str
    organisation_name: str
    registration_number: str
    organisation_address: str
    status: str


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


class ConcertPoster(SQLModel, table=True):
    """Poster image associated with one concert."""

    id: int | None = Field(default=None, primary_key=True)
    concert_id: int = Field(
        foreign_key="concert.id",
        index=True,
        unique=True,
    )
    filename: str


class TicketSalesPeriod(SQLModel, table=True):
    """Ticket sales dates configured for one concert."""

    id: int | None = Field(default=None, primary_key=True)
    concert_id: int = Field(
        foreign_key="concert.id",
        index=True,
        unique=True,
    )
    sales_start: str
    sales_end: str


class ConcertApproval(SQLModel, table=True):
    """Approval status for a submitted concert."""

    id: int | None = Field(default=None, primary_key=True)
    concert_id: int = Field(
        foreign_key="concert.id",
        index=True,
        unique=True,
    )
    status: str = Field(default="pending")


class TicketBase(SQLModel):
    concert_id: int = Field(foreign_key="concert.id")
    category: str
    price: float
    quantity: int


class Ticket(TicketBase, table=True):
    """Database table."""

    id: int | None = Field(default=None, primary_key=True)
    sold: int = Field(default=0)


class TicketCreate(TicketBase):
    """What the organiser sends."""


class TicketRead(TicketBase):
    """What the API returns."""

    id: int
    sold: int


class BookingBase(SQLModel):
    ticket_id: int = Field(foreign_key="ticket.id")
    attendee: str
    quantity: int


class Booking(BookingBase, table=True):
    """Database table."""

    id: int | None = Field(default=None, primary_key=True)
    user_id: int | None = Field(
        default=None,
        foreign_key="user.id",
        index=True,
    )
    status: str = Field(default="pending_payment")


class BookingCreate(BookingBase):
    """What the attendee sends."""


class BookingRead(BookingBase):
    """What the API returns."""

    id: int
    status: str


class PaymentProof(SQLModel, table=True):
    """US24 — Proof of payment attached to a booking."""

    id: int | None = Field(default=None, primary_key=True)
    booking_id: int = Field(foreign_key="booking.id")
    filename: str


class PaymentProofRead(SQLModel):
    id: int
    booking_id: int
    filename: str


class ETicket(SQLModel, table=True):
    """Electronic ticket generated after payment approval."""

    id: int | None = Field(
        default=None,
        primary_key=True,
    )
    booking_id: int = Field(
        foreign_key="booking.id",
        index=True,
    )
    ticket_code: str = Field(
        index=True,
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(
            timezone.utc,
        )
    )
