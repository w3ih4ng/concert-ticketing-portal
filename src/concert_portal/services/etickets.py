from uuid import uuid4

from sqlmodel import Session, select

from concert_portal.models import Booking, ETicket


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
