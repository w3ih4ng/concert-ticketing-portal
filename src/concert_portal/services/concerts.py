from fastapi import HTTPException
from sqlmodel import Session, select

from concert_portal.models import Concert, ConcertCreate, Ticket, TicketCreate
from concert_portal.validation import validate_concert_fields, validate_ticket_fields


def create_concert_record(data: ConcertCreate, session: Session) -> Concert:
    """Create a validated concert event."""

    errors = validate_concert_fields(
        data.title,
        data.date,
        data.venue,
        data.organiser,
    )

    if errors:
        raise HTTPException(
            status_code=422,
            detail=errors,
        )

    concert = Concert(
        title=data.title.strip(),
        date=data.date.strip(),
        venue=data.venue.strip(),
        organiser=data.organiser.strip(),
    )

    session.add(concert)
    session.commit()
    session.refresh(concert)

    return concert


def create_ticket_record(data: TicketCreate, session: Session) -> Ticket:
    """Create a validated ticket category."""

    concert = session.get(
        Concert,
        data.concert_id,
    )

    if concert is None:
        raise HTTPException(
            status_code=404,
            detail="Concert not found",
        )

    errors, category, price, quantity = validate_ticket_fields(
        data.category,
        data.price,
        data.quantity,
    )

    if errors:
        raise HTTPException(
            status_code=422,
            detail=errors,
        )

    if price is None or quantity is None:
        raise HTTPException(
            status_code=422,
            detail="Invalid ticket data",
        )

    ticket = Ticket(
        concert_id=data.concert_id,
        category=category,
        price=price,
        quantity=quantity,
    )

    session.add(ticket)
    session.commit()
    session.refresh(ticket)

    return ticket


def get_concerts(session: Session) -> list[Concert]:
    """Return all concerts."""

    return list(
        session.exec(
            select(Concert),
        ).all()
    )


def get_concert_tickets(
    concert_id: int,
    session: Session,
) -> list[Ticket]:
    """Return all ticket categories belonging to a concert."""

    return list(
        session.exec(
            select(Ticket).where(
                Ticket.concert_id == concert_id,
            )
        ).all()
    )


def get_concert_by_id(
    concert_id: int,
    session: Session,
) -> Concert | None:
    """Return a concert by id."""

    return session.get(
        Concert,
        concert_id,
    )


def save_concert_form(
    title: str,
    date: str,
    venue: str,
    organiser: str,
    session: Session,
) -> Concert:
    """Persist a concert created from the HTML form."""

    errors = validate_concert_fields(
        title,
        date,
        venue,
        organiser,
    )

    if errors:
        raise HTTPException(
            status_code=422,
            detail=errors,
        )

    concert = Concert(
        title=title.strip(),
        date=date.strip(),
        venue=venue.strip(),
        organiser=organiser.strip(),
    )

    session.add(concert)
    session.commit()
    session.refresh(concert)

    return concert


def update_concert_record(
    concert_id: int,
    title: str,
    date: str,
    venue: str,
    organiser: str,
    session: Session,
) -> Concert:
    """Update an existing concert after validating its fields."""

    concert = session.get(
        Concert,
        concert_id,
    )

    if concert is None:
        raise HTTPException(
            status_code=404,
            detail="Concert not found",
        )

    errors = validate_concert_fields(
        title,
        date,
        venue,
        organiser,
    )

    if errors:
        raise HTTPException(
            status_code=422,
            detail=errors,
        )

    concert.title = title.strip()
    concert.date = date.strip()
    concert.venue = venue.strip()
    concert.organiser = organiser.strip()

    session.add(concert)
    session.commit()
    session.refresh(concert)

    return concert


def save_ticket_form(
    concert_id: int,
    category: str,
    price: str | int | float,
    quantity: str | int | float,
    session: Session,
) -> Ticket:
    """Persist a ticket created from the HTML form."""

    errors, cleaned_category, parsed_price, parsed_quantity = validate_ticket_fields(
        category,
        price,
        quantity,
    )

    if errors:
        raise HTTPException(
            status_code=422,
            detail=errors,
        )

    if parsed_price is None or parsed_quantity is None:
        raise HTTPException(
            status_code=422,
            detail="Invalid ticket data",
        )

    ticket = Ticket(
        concert_id=concert_id,
        category=cleaned_category,
        price=parsed_price,
        quantity=parsed_quantity,
    )

    session.add(ticket)
    session.commit()
    session.refresh(ticket)

    return ticket
