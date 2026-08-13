from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException
from sqlmodel import Session, select

from concert_portal.models import (
    Booking,
    Concert,
    ETicket,
    Ticket,
)


@dataclass(frozen=True)
class ETicketView:
    """Information displayed on an attendee e-ticket."""

    eticket: ETicket
    booking: Booking
    ticket: Ticket
    concert: Concert


def _generate_ticket_code(
    session: Session,
) -> str:
    """Generate a unique public verification code."""

    while True:
        code = f"ET-{uuid4().hex[:12].upper()}"

        existing = session.exec(
            select(ETicket).where(
                ETicket.ticket_code == code,
            )
        ).first()

        if existing is None:
            return code


def get_eticket_for_booking(
    booking_id: int,
    session: Session,
) -> ETicket | None:
    """Return the e-ticket generated for a booking."""

    return session.exec(
        select(ETicket).where(
            ETicket.booking_id == booking_id,
        )
    ).first()


def generate_eticket(
    booking: Booking,
    session: Session,
) -> ETicket:
    """Generate one e-ticket for a confirmed booking."""

    if booking.id is None:
        raise ValueError("Booking must be saved before generating an e-ticket.")

    existing = get_eticket_for_booking(
        booking.id,
        session,
    )

    if existing is not None:
        return existing

    eticket = ETicket(
        booking_id=booking.id,
        ticket_code=_generate_ticket_code(
            session,
        ),
    )

    session.add(
        eticket,
    )

    return eticket


def get_attendee_eticket(
    booking_id: int,
    user_id: int,
    session: Session,
) -> ETicketView:
    """Return an e-ticket belonging to the logged-in attendee."""

    booking = session.get(
        Booking,
        booking_id,
    )

    if booking is None or booking.user_id != user_id:
        raise HTTPException(
            status_code=404,
            detail="E-ticket not found.",
        )

    if booking.status != "confirmed":
        raise HTTPException(
            status_code=404,
            detail="E-ticket not found.",
        )

    eticket = get_eticket_for_booking(
        booking_id,
        session,
    )

    if eticket is None:
        raise HTTPException(
            status_code=404,
            detail="E-ticket not found.",
        )

    ticket = session.get(
        Ticket,
        booking.ticket_id,
    )

    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found.",
        )

    concert = session.get(
        Concert,
        ticket.concert_id,
    )

    if concert is None:
        raise HTTPException(
            status_code=404,
            detail="Concert not found.",
        )

    return ETicketView(
        eticket=eticket,
        booking=booking,
        ticket=ticket,
        concert=concert,
    )


def verify_eticket_code(
    ticket_code: str,
    session: Session,
) -> ETicketView | None:
    """Return confirmed e-ticket details for staff verification."""

    normalized_code = ticket_code.strip().upper()

    if not normalized_code:
        return None

    eticket = session.exec(
        select(ETicket).where(
            ETicket.ticket_code == normalized_code,
        )
    ).first()

    if eticket is None:
        return None

    booking = session.get(
        Booking,
        eticket.booking_id,
    )

    if booking is None or booking.status != "confirmed":
        return None

    ticket = session.get(
        Ticket,
        booking.ticket_id,
    )

    if ticket is None:
        return None

    concert = session.get(
        Concert,
        ticket.concert_id,
    )

    if concert is None:
        return None

    return ETicketView(
        eticket=eticket,
        booking=booking,
        ticket=ticket,
        concert=concert,
    )


def check_in_eticket(
    ticket_code: str,
    session: Session,
) -> ETicketView:
    """Mark a valid e-ticket as checked in."""

    result = verify_eticket_code(
        ticket_code,
        session,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Valid e-ticket not found.",
        )

    if result.eticket.checked_in:
        raise HTTPException(
            status_code=409,
            detail="This e-ticket has already been checked in.",
        )

    result.eticket.checked_in = True
    result.eticket.checked_in_at = datetime.now(
        timezone.utc,
    )

    session.add(
        result.eticket,
    )
    session.commit()
    session.refresh(
        result.eticket,
    )

    return result
