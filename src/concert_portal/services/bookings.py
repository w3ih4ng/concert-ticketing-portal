from dataclasses import dataclass

from fastapi import HTTPException
from sqlmodel import Session, col, select

from concert_portal.models import Booking, BookingCreate, Concert, Ticket
from concert_portal.services.sales_periods import is_ticket_sales_open
from concert_portal.validation import validate_booking_fields


@dataclass(frozen=True)
class BookingHistoryItem:
    """Booking information displayed on the attendee history page."""

    booking: Booking
    ticket: Ticket
    concert: Concert


def create_booking_record(
    data: BookingCreate,
    session: Session,
    *,
    user_id: int | None = None,
) -> Booking:
    """Create a validated booking while preventing overselling."""

    ticket = session.get(
        Ticket,
        data.ticket_id,
    )

    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found",
        )

    if not is_ticket_sales_open(
        ticket.concert_id,
        session,
    ):
        raise HTTPException(
            status_code=409,
            detail=("Ticket sales are not open " "for this concert."),
        )

    remaining = max(
        ticket.quantity - ticket.sold,
        0,
    )

    errors, attendee, quantity = validate_booking_fields(
        data.attendee,
        data.quantity,
        remaining,
    )

    if errors:
        quantity_error = errors.get(
            "quantity",
            "",
        )
        attendee_error = errors.get(
            "attendee",
            "",
        )

        if "remaining" in quantity_error:
            raise HTTPException(
                status_code=409,
                detail={
                    "quantity": quantity_error,
                    "remaining": remaining,
                },
            )

        if "at least 1" in quantity_error:
            raise HTTPException(
                status_code=400,
                detail={
                    "quantity": quantity_error,
                },
            )

        if attendee_error:
            raise HTTPException(
                status_code=422,
                detail={
                    "attendee": attendee_error,
                },
            )

        raise HTTPException(
            status_code=422,
            detail=errors,
        )

    if quantity is None:
        raise HTTPException(
            status_code=422,
            detail={"quantity": ("Invalid booking quantity")},
        )

    new_sold_quantity = ticket.sold + quantity

    if new_sold_quantity > ticket.quantity:
        raise HTTPException(
            status_code=409,
            detail={
                "quantity": ("Not enough tickets remaining."),
                "remaining": remaining,
            },
        )

    booking = Booking(
        ticket_id=data.ticket_id,
        attendee=attendee,
        quantity=quantity,
        user_id=user_id,
    )

    ticket.sold = new_sold_quantity

    session.add(
        booking,
    )
    session.add(
        ticket,
    )
    session.commit()
    session.refresh(
        booking,
    )

    return booking


def get_attendee_booking_history(
    user_id: int,
    session: Session,
) -> list[BookingHistoryItem]:
    """Retrieve bookings belonging to one attendee account."""

    bookings = session.exec(
        select(Booking)
        .where(
            Booking.user_id == user_id,
        )
        .order_by(
            col(Booking.id).desc(),
        )
    ).all()

    history: list[BookingHistoryItem] = []

    for booking in bookings:
        ticket = session.get(
            Ticket,
            booking.ticket_id,
        )

        if ticket is None:
            continue

        concert = session.get(
            Concert,
            ticket.concert_id,
        )

        if concert is None:
            continue

        history.append(
            BookingHistoryItem(
                booking=booking,
                ticket=ticket,
                concert=concert,
            )
        )

    return history


def cancel_booking_record(
    booking_id: int,
    session: Session,
) -> Booking:
    """Cancel a pending booking and restore its reserved ticket quantity."""

    booking = session.get(
        Booking,
        booking_id,
    )

    if booking is None:
        raise HTTPException(
            status_code=404,
            detail="Booking not found",
        )

    if booking.status == "cancelled":
        raise HTTPException(
            status_code=409,
            detail=("This booking has already " "been cancelled."),
        )

    if booking.status != "pending_payment":
        raise HTTPException(
            status_code=409,
            detail=("Only bookings that are still " "pending payment can be cancelled."),
        )

    ticket = session.get(
        Ticket,
        booking.ticket_id,
    )

    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found",
        )

    ticket.sold = max(
        ticket.sold - booking.quantity,
        0,
    )

    booking.status = "cancelled"

    session.add(
        ticket,
    )
    session.add(
        booking,
    )
    session.commit()
    session.refresh(
        booking,
    )

    return booking
