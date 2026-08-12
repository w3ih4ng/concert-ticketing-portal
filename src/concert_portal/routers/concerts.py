from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import Session

from concert_portal.database import get_session
from concert_portal.models import (
    Concert,
    ConcertCreate,
    ConcertRead,
    Ticket,
    TicketCreate,
    TicketRead,
)
from concert_portal.services.concerts import (
    create_concert_record,
    create_ticket_record,
    get_concert_by_id,
    get_concert_tickets,
    get_concerts,
    save_concert_form,
    save_ticket_form,
    update_concert_record,
)
from concert_portal.validation import (
    validate_concert_fields,
    validate_ticket_fields,
)
from concert_portal.web import templates

router = APIRouter()


@router.post(
    "/concerts",
    response_model=ConcertRead,
    status_code=201,
)
def create_concert(
    data: ConcertCreate,
    session: Session = Depends(get_session),
) -> Concert:
    """US07 — Organiser creates a concert event."""

    return create_concert_record(
        data,
        session,
    )


@router.get(
    "/",
    response_class=HTMLResponse,
)
def concerts_page(
    request: Request,
    error: str | None = None,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Show all concerts."""

    concerts = get_concerts(
        session,
    )

    return templates.TemplateResponse(
        request,
        "concerts.html",
        {
            "concerts": concerts,
            "error": _error_message(error),
        },
    )


@router.get(
    "/concerts/new",
    response_class=HTMLResponse,
)
def concert_new_form(
    request: Request,
) -> HTMLResponse:
    """Show the create-concert form."""

    return templates.TemplateResponse(
        request,
        "concert_new.html",
        {
            "errors": {},
            "values": {},
        },
    )


@router.post(
    "/concerts/new",
    response_model=None,
)
def concert_new_submit(
    request: Request,
    title: str = Form(""),
    date: str = Form(""),
    venue: str = Form(""),
    organiser: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse | HTMLResponse:
    """Handle the HTML form submission."""

    errors = validate_concert_fields(
        title,
        date,
        venue,
        organiser,
    )

    if errors:
        return templates.TemplateResponse(
            request,
            "concert_new.html",
            {
                "errors": errors,
                "values": {
                    "title": title,
                    "date": date,
                    "venue": venue,
                    "organiser": organiser,
                },
            },
            status_code=422,
        )

    concert = save_concert_form(
        title,
        date,
        venue,
        organiser,
        session,
    )

    return RedirectResponse(
        url=f"/concerts/{concert.id}",
        status_code=303,
    )


@router.post(
    "/tickets",
    response_model=TicketRead,
    status_code=201,
)
def create_ticket(
    data: TicketCreate,
    session: Session = Depends(get_session),
) -> Ticket:
    """US15/16/17 — Create a validated ticket category."""

    return create_ticket_record(
        data,
        session,
    )


@router.get(
    "/concerts/{concert_id}/tickets",
    response_model=list[TicketRead],
)
def list_tickets(
    concert_id: int,
    session: Session = Depends(get_session),
) -> list[Ticket]:
    """List all ticket categories for a concert."""

    return get_concert_tickets(
        concert_id,
        session,
    )


@router.get(
    "/concerts/{concert_id}/tickets/new",
    response_class=HTMLResponse,
)
def ticket_new_form(
    concert_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Show the add-ticket-category form for a concert."""

    concert = get_concert_by_id(
        concert_id,
        session,
    )

    if concert is None:
        raise HTTPException(
            status_code=404,
            detail="Concert not found",
        )

    return templates.TemplateResponse(
        request,
        "ticket_new.html",
        {
            "concert": concert,
            "errors": {},
            "values": {},
        },
    )


@router.post(
    "/concerts/{concert_id}/tickets/new",
    response_model=None,
)
def ticket_new_submit(
    concert_id: int,
    request: Request,
    category: str = Form(...),
    price: str = Form(...),
    quantity: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse | HTMLResponse:
    """Validate and process the HTML ticket form."""

    concert = get_concert_by_id(
        concert_id,
        session,
    )

    if concert is None:
        return RedirectResponse(
            url="/?error=concert_missing",
            status_code=303,
        )

    errors, cleaned_category, parsed_price, parsed_quantity = validate_ticket_fields(
        category,
        price,
        quantity,
    )

    if errors:
        return templates.TemplateResponse(
            request,
            "ticket_new.html",
            {
                "concert": concert,
                "errors": errors,
                "values": {
                    "category": category,
                    "price": price,
                    "quantity": quantity,
                },
            },
            status_code=422,
        )

    if parsed_price is None or parsed_quantity is None:
        raise HTTPException(
            status_code=422,
            detail="Invalid ticket data",
        )

    save_ticket_form(
        concert_id,
        cleaned_category,
        parsed_price,
        parsed_quantity,
        session,
    )

    return RedirectResponse(
        url=f"/concerts/{concert_id}",
        status_code=303,
    )


@router.get(
    "/concerts/{concert_id}/edit",
    response_class=HTMLResponse,
)
def concert_edit_form(
    concert_id: int,
    request: Request,
    updated: bool = False,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """US08 — Show the concert edit form."""

    concert = get_concert_by_id(
        concert_id,
        session,
    )

    if concert is None:
        raise HTTPException(
            status_code=404,
            detail="Concert not found",
        )

    return templates.TemplateResponse(
        request,
        "concert_edit.html",
        {
            "concert": concert,
            "errors": {},
            "values": {
                "title": concert.title,
                "date": concert.date,
                "venue": concert.venue,
                "organiser": concert.organiser,
            },
            "updated": updated,
        },
    )


@router.post(
    "/concerts/{concert_id}/edit",
    response_model=None,
)
def concert_edit_submit(
    concert_id: int,
    request: Request,
    title: str = Form(""),
    date: str = Form(""),
    venue: str = Form(""),
    organiser: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse | HTMLResponse:
    """Validate and save edited concert details."""

    concert = get_concert_by_id(
        concert_id,
        session,
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

    values = {
        "title": title,
        "date": date,
        "venue": venue,
        "organiser": organiser,
    }

    if errors:
        return templates.TemplateResponse(
            request,
            "concert_edit.html",
            {
                "concert": concert,
                "errors": errors,
                "values": values,
                "updated": False,
            },
            status_code=422,
        )

    update_concert_record(
        concert_id,
        title,
        date,
        venue,
        organiser,
        session,
    )

    return RedirectResponse(
        url=f"/concerts/{concert_id}/edit?updated=true",
        status_code=303,
    )


@router.get(
    "/concerts/{concert_id}",
    response_class=HTMLResponse,
)
def concert_detail_page(
    concert_id: int,
    request: Request,
    error: str | None = None,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """US14 — Attendee views concert details and ticket options."""

    concert = get_concert_by_id(
        concert_id,
        session,
    )

    if concert is None:
        raise HTTPException(
            status_code=404,
            detail="Concert not found",
        )

    tickets = get_concert_tickets(
        concert_id,
        session,
    )

    return templates.TemplateResponse(
        request,
        "concert_detail.html",
        {
            "concert": concert,
            "tickets": list(tickets),
            "error": _error_message(error),
        },
    )


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


def _error_message(
    code: str | None,
) -> str | None:
    """Map a short error code from the query string to display text."""

    if code is None:
        return None

    return BOOKING_ERROR_MESSAGES.get(
        code,
        "Something went wrong with that booking.",
    )
