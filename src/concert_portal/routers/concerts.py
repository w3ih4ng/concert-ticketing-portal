from pathlib import Path

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    RedirectResponse,
    Response,
)
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
from concert_portal.services.concert_approvals import (
    ensure_concert_is_editable,
    get_concert_approval_status,
    is_concert_locked,
    submit_concert_for_approval,
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
from concert_portal.services.posters import (
    generate_concert_poster_filename,
    get_concert_poster,
    get_concert_poster_path,
    save_concert_poster,
    validate_concert_poster,
)
from concert_portal.services.sales_periods import (
    get_ticket_sales_period,
    get_ticket_sales_status,
    is_ticket_sales_open,
    save_ticket_sales_period,
    validate_ticket_sales_period,
)
from concert_portal.validation import (
    validate_concert_fields,
    validate_ticket_fields,
)
from concert_portal.web import UPLOAD_DIR, templates

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
) -> Response:
    """Show all concerts."""

    concerts = get_concerts(
        session,
    )

    return templates.TemplateResponse(
        request,
        "concerts.html",
        {
            "concerts": concerts,
            "error": _error_message(
                error,
            ),
        },
    )


@router.get(
    "/concerts/new",
    response_class=HTMLResponse,
)
def concert_new_form(
    request: Request,
) -> Response:
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
) -> RedirectResponse | Response:
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

    ensure_concert_is_editable(
        data.concert_id,
        session,
    )

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
) -> Response:
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

    if is_concert_locked(
        concert_id,
        session,
    ):
        return RedirectResponse(
            url=(f"/concerts/{concert_id}" "?approval_error=locked"),
            status_code=303,
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
) -> RedirectResponse | Response:
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

    if is_concert_locked(
        concert_id,
        session,
    ):
        return RedirectResponse(
            url=(f"/concerts/{concert_id}" "?approval_error=locked"),
            status_code=303,
        )

    (
        errors,
        cleaned_category,
        parsed_price,
        parsed_quantity,
    ) = validate_ticket_fields(
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
) -> Response:
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

    if is_concert_locked(
        concert_id,
        session,
    ):
        return RedirectResponse(
            url=(f"/concerts/{concert_id}" "?approval_error=locked"),
            status_code=303,
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

    if is_concert_locked(
        concert_id,
        session,
    ):
        return RedirectResponse(
            url=(f"/concerts/{concert_id}" "?approval_error=locked"),
            status_code=303,
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


@router.post(
    "/concerts/{concert_id}/poster",
    response_model=None,
)
async def upload_concert_poster(
    concert_id: int,
    poster: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """US09 — Upload or replace a concert poster."""

    concert = get_concert_by_id(
        concert_id,
        session,
    )

    if concert is None:
        raise HTTPException(
            status_code=404,
            detail="Concert not found.",
        )

    if is_concert_locked(
        concert_id,
        session,
    ):
        return RedirectResponse(
            url=(f"/concerts/{concert_id}" "?approval_error=locked"),
            status_code=303,
        )

    content = await poster.read()

    try:
        extension = validate_concert_poster(
            filename=poster.filename,
            content_type=poster.content_type,
            content=content,
        )

    except HTTPException as exc:
        return RedirectResponse(
            url=(f"/concerts/{concert_id}" f"?poster_error={exc.status_code}"),
            status_code=303,
        )

    stored_filename = generate_concert_poster_filename(
        concert_id,
        extension,
    )

    UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    stored_path = UPLOAD_DIR / Path(stored_filename).name

    stored_path.write_bytes(
        content,
    )

    try:
        save_concert_poster(
            concert_id,
            stored_filename,
            session,
        )

    except Exception:
        if stored_path.is_file():
            stored_path.unlink()

        raise

    return RedirectResponse(
        url=f"/concerts/{concert_id}?poster_updated=true",
        status_code=303,
    )


@router.get(
    "/concerts/{concert_id}/poster",
    response_model=None,
)
def concert_poster_file(
    concert_id: int,
    session: Session = Depends(get_session),
) -> Response:
    """Return the stored poster image for a concert."""

    poster = get_concert_poster(
        concert_id,
        session,
    )

    if poster is None:
        raise HTTPException(
            status_code=404,
            detail="Concert poster not found.",
        )

    path = get_concert_poster_path(
        poster,
    )

    return FileResponse(
        path,
    )


@router.get(
    "/concerts/{concert_id}/sales-period",
    response_class=HTMLResponse,
)
def ticket_sales_period_form(
    concert_id: int,
    request: Request,
    updated: bool = False,
    session: Session = Depends(get_session),
) -> Response:
    """US10 — Show ticket sales period form."""

    concert = get_concert_by_id(
        concert_id,
        session,
    )

    if concert is None:
        raise HTTPException(
            status_code=404,
            detail="Concert not found",
        )

    if is_concert_locked(
        concert_id,
        session,
    ):
        return RedirectResponse(
            url=(f"/concerts/{concert_id}" "?approval_error=locked"),
            status_code=303,
        )

    sales_period = get_ticket_sales_period(
        concert_id,
        session,
    )

    return templates.TemplateResponse(
        request,
        "ticket_sales_period.html",
        {
            "concert": concert,
            "errors": {},
            "values": {
                "sales_start": (sales_period.sales_start if sales_period is not None else ""),
                "sales_end": (sales_period.sales_end if sales_period is not None else ""),
            },
            "updated": updated,
        },
    )


@router.post(
    "/concerts/{concert_id}/sales-period",
    response_model=None,
)
def ticket_sales_period_submit(
    concert_id: int,
    request: Request,
    sales_start: str = Form(""),
    sales_end: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse | HTMLResponse:
    """Validate and save ticket sales period."""

    concert = get_concert_by_id(
        concert_id,
        session,
    )

    if concert is None:
        raise HTTPException(
            status_code=404,
            detail="Concert not found",
        )

    if is_concert_locked(
        concert_id,
        session,
    ):
        return RedirectResponse(
            url=(f"/concerts/{concert_id}" "?approval_error=locked"),
            status_code=303,
        )

    errors = validate_ticket_sales_period(
        sales_start,
        sales_end,
    )

    values = {
        "sales_start": sales_start,
        "sales_end": sales_end,
    }

    if errors:
        return templates.TemplateResponse(
            request,
            "ticket_sales_period.html",
            {
                "concert": concert,
                "errors": errors,
                "values": values,
                "updated": False,
            },
            status_code=422,
        )

    save_ticket_sales_period(
        concert_id,
        sales_start,
        sales_end,
        session,
    )

    return RedirectResponse(
        url=(f"/concerts/{concert_id}" "/sales-period?updated=true"),
        status_code=303,
    )


@router.post(
    "/concerts/{concert_id}/submit",
    response_model=None,
)
def submit_concert(
    concert_id: int,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """US11 — Submit a concert for administrator approval."""

    try:
        submit_concert_for_approval(
            concert_id,
            session,
        )

    except HTTPException as exc:
        if exc.status_code == 404:
            raise

        return RedirectResponse(
            url=(f"/concerts/{concert_id}" "?approval_error=already_submitted"),
            status_code=303,
        )

    return RedirectResponse(
        url=(f"/concerts/{concert_id}" "?submitted=true"),
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
    poster_error: int | None = None,
    poster_updated: bool = False,
    submitted: bool = False,
    approval_error: str | None = None,
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

    poster = get_concert_poster(
        concert_id,
        session,
    )

    sales_period = get_ticket_sales_period(
        concert_id,
        session,
    )

    sales_open = is_ticket_sales_open(
        concert_id,
        session,
    )

    sales_status = get_ticket_sales_status(
        concert_id,
        session,
    )

    approval_status = get_concert_approval_status(
        concert_id,
        session,
    )

    concert_locked = is_concert_locked(
        concert_id,
        session,
    )

    return templates.TemplateResponse(
        request,
        "concert_detail.html",
        {
            "concert": concert,
            "tickets": list(tickets),
            "poster": poster,
            "poster_error": _poster_error_message(
                poster_error,
            ),
            "poster_updated": poster_updated,
            "sales_period": sales_period,
            "sales_open": sales_open,
            "sales_status": sales_status,
            "approval_status": approval_status,
            "concert_locked": concert_locked,
            "submitted": submitted,
            "approval_error": _approval_error_message(
                approval_error,
            ),
            "error": _error_message(
                error,
            ),
        },
    )


BOOKING_ERROR_MESSAGES = {
    "bad_quantity": "Quantity must be at least 1.",
    "blank_attendee": "Attendee name cannot be blank.",
    "invalid_attendee": "Enter a valid attendee name.",
    "not_found": "That ticket could not be found.",
    "oversold": "Not enough tickets left for that quantity.",
    "concert_missing": "That concert could not be found.",
    "sales_closed": ("Ticket sales are not currently open " "for this concert."),
}

POSTER_ERROR_MESSAGES = {
    413: "Concert poster files must not exceed 5 MB.",
    422: ("Concert poster must be a valid JPG, " "JPEG or PNG image."),
}

APPROVAL_ERROR_MESSAGES = {
    "locked": ("This concert is locked while it is " "awaiting approval or after approval."),
    "already_submitted": ("This concert has already been submitted " "for approval."),
}


def _error_message(
    code: str | None,
) -> str | None:
    """Map a booking error code to display text."""

    if code is None:
        return None

    return BOOKING_ERROR_MESSAGES.get(
        code,
        "Something went wrong with that booking.",
    )


def _poster_error_message(
    status_code: int | None,
) -> str | None:
    """Map poster upload errors to display text."""

    if status_code is None:
        return None

    return POSTER_ERROR_MESSAGES.get(
        status_code,
        "The concert poster could not be uploaded.",
    )


def _approval_error_message(
    code: str | None,
) -> str | None:
    """Map concert approval errors to display text."""

    if code is None:
        return None

    return APPROVAL_ERROR_MESSAGES.get(
        code,
        "The approval request could not be completed.",
    )
