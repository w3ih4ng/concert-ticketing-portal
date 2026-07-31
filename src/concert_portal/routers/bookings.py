from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlmodel import Session, select

from concert_portal.database import get_session
from concert_portal.models import (
    Booking,
    BookingCreate,
    BookingRead,
    PaymentProof,
    Ticket,
)
from concert_portal.security import get_session_user, role_redirect_url
from concert_portal.services.bookings import (
    cancel_booking_record,
    create_booking_record,
    get_attendee_booking_history,
)
from concert_portal.validation import validate_booking_fields
from concert_portal.web import templates

router = APIRouter()

BOOKING_ERROR_CODES = {
    400: "bad_quantity",
    404: "not_found",
    409: "oversold",
}

BOOKING_ERROR_MESSAGES = {
    "bad_quantity": "Quantity must be at least 1.",
    "blank_attendee": "Attendee name cannot be blank.",
    "invalid_attendee": "Enter a valid attendee name.",
    "not_found": "That ticket could not be found.",
    "oversold": "Not enough tickets left for that quantity.",
    "concert_missing": "That concert could not be found.",
}

CANCELLATION_MESSAGES = {
    "cancelled": ("Booking cancelled successfully. " "The reserved tickets are available again."),
    "not_pending": ("Only bookings that are still pending payment can be cancelled."),
    "already_cancelled": "This booking has already been cancelled.",
}


def _error_message(code: str | None) -> str | None:
    """Map a short error code from the query string to display text."""

    if code is None:
        return None

    return BOOKING_ERROR_MESSAGES.get(
        code,
        "Something went wrong with that booking.",
    )


def _cancellation_message(code: str | None) -> str | None:
    """Map a cancellation result code to a readable message."""

    if code is None:
        return None

    return CANCELLATION_MESSAGES.get(
        code,
        "Something went wrong while cancelling the booking.",
    )


@router.get("/bookings/history", response_class=HTMLResponse)
def booking_history_page(
    request: Request,
    session: Session = Depends(get_session),
) -> Response:
    """US22 — Show bookings belonging to the logged-in attendee."""

    current_user = get_session_user(request, session)

    if current_user is None:
        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    if current_user.role != "attendee":
        return RedirectResponse(
            url=role_redirect_url(current_user.role),
            status_code=303,
        )

    if current_user.id is None:
        request.session.clear()

        return RedirectResponse(
            url="/login",
            status_code=303,
        )

    history = get_attendee_booking_history(
        current_user.id,
        session,
    )

    return templates.TemplateResponse(
        request,
        "booking_history.html",
        {
            "user": current_user,
            "history": history,
        },
    )


@router.post(
    "/bookings",
    response_model=BookingRead,
    status_code=201,
)
def create_booking(
    data: BookingCreate,
    session: Session = Depends(get_session),
) -> Booking:
    """Create a validated booking while preventing overselling."""

    return create_booking_record(data, session)


@router.post("/bookings/new")
def booking_new_submit(
    request: Request,
    ticket_id: int = Form(...),
    attendee: str = Form(...),
    quantity: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Validate and process the HTML booking form."""

    current_user = get_session_user(request, session)

    booking_user_id: int | None = None
    booking_attendee = attendee

    if current_user is not None and current_user.role == "attendee":
        booking_user_id = current_user.id
        booking_attendee = current_user.name

    ticket = session.get(Ticket, ticket_id)

    if ticket is None:
        return RedirectResponse(
            url="/?error=not_found",
            status_code=303,
        )

    remaining = max(ticket.quantity - ticket.sold, 0)

    errors, cleaned_attendee, parsed_quantity = validate_booking_fields(
        booking_attendee,
        quantity,
        remaining,
    )

    if errors:
        if "attendee" in errors:
            attendee_error = errors["attendee"]

            if "blank" in attendee_error:
                error_code = "blank_attendee"
            else:
                error_code = "invalid_attendee"
        elif "remaining" in errors.get("quantity", ""):
            error_code = "oversold"
        else:
            error_code = "bad_quantity"

        return RedirectResponse(
            url=(f"/concerts/{ticket.concert_id}" f"?error={error_code}"),
            status_code=303,
        )

    if parsed_quantity is None:
        return RedirectResponse(
            url=(f"/concerts/{ticket.concert_id}" "?error=bad_quantity"),
            status_code=303,
        )

    try:
        booking = create_booking_record(
            BookingCreate(
                ticket_id=ticket_id,
                attendee=cleaned_attendee,
                quantity=parsed_quantity,
            ),
            session,
            user_id=booking_user_id,
        )
    except HTTPException as exc:
        error_code = BOOKING_ERROR_CODES.get(
            exc.status_code,
            "bad_quantity",
        )

        return RedirectResponse(
            url=(f"/concerts/{ticket.concert_id}" f"?error={error_code}"),
            status_code=303,
        )

    return RedirectResponse(
        url=f"/bookings/{booking.id}",
        status_code=303,
    )


@router.get(
    "/bookings/{booking_id}",
    response_class=HTMLResponse,
)
def booking_detail_page(
    booking_id: int,
    request: Request,
    message: str | None = None,
    error: str | None = None,
    payment_error: str | None = None,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Show a booking, payment proof status, and cancellation result."""

    booking = session.get(Booking, booking_id)

    if booking is None:
        raise HTTPException(
            status_code=404,
            detail="Booking not found",
        )

    proof = session.exec(select(PaymentProof).where(PaymentProof.booking_id == booking_id)).first()

    ticket = session.get(Ticket, booking.ticket_id)

    return templates.TemplateResponse(
        request,
        "booking_detail.html",
        {
            "booking": booking,
            "proof": proof,
            "ticket": ticket,
            "message": _cancellation_message(message),
            "error": _cancellation_message(error),
            "payment_error": payment_error,
        },
    )


@router.post("/bookings/{booking_id}/cancel/form")
def cancel_booking_submit(
    booking_id: int,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Process booking cancellation from the booking detail page."""

    try:
        cancel_booking_record(
            booking_id,
            session,
        )
    except HTTPException as exc:
        if exc.status_code == 404:
            raise

        detail = str(exc.detail)

        if "already been cancelled" in detail:
            error_code = "already_cancelled"
        else:
            error_code = "not_pending"

        return RedirectResponse(
            url=(f"/bookings/{booking_id}" f"?error={error_code}"),
            status_code=303,
        )

    return RedirectResponse(
        url=(f"/bookings/{booking_id}" "?message=cancelled"),
        status_code=303,
    )


@router.post(
    "/bookings/{booking_id}/cancel",
    response_model=BookingRead,
)
def cancel_booking(
    booking_id: int,
    session: Session = Depends(get_session),
) -> Booking:
    """US23 — Cancel a booking that is still pending payment."""

    return cancel_booking_record(
        booking_id,
        session,
    )
