import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import date as date_cls
from decimal import Decimal, InvalidOperation
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pwdlib import PasswordHash
from sqlmodel import Session, select

from concert_portal.database import get_session, init_db
from concert_portal.models import (
    AttendeeCreate,
    Booking,
    BookingCreate,
    BookingRead,
    Concert,
    ConcertCreate,
    ConcertRead,
    PaymentProof,
    Ticket,
    TicketCreate,
    TicketRead,
    User,
    UserRead,
)

# --- SCRUM-11: Attendee registration ---

password_hash = PasswordHash.recommended()

USER_NAME_MIN_LEN = 2
USER_NAME_MAX_LEN = 100
PASSWORD_MIN_LEN = 8
PASSWORD_MAX_LEN = 128

EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)

PHONE_PATTERN = re.compile(r"^[0-9+()\-\s]+$")


def normalize_email(email: str) -> str:
    """Trim and normalize an email address for storage and comparison."""

    return email.strip().lower()


def validate_attendee_registration(
    name: str,
    email: str,
    phone: str,
    password: str,
) -> tuple[dict[str, str], dict[str, str]]:
    """Validate and clean attendee registration values."""

    errors: dict[str, str] = {}

    cleaned_name = " ".join(name.split())
    cleaned_email = normalize_email(email)
    cleaned_phone = phone.strip()

    if not cleaned_name:
        errors["name"] = "Name cannot be blank."
    elif len(cleaned_name) < USER_NAME_MIN_LEN:
        errors["name"] = f"Name must be at least {USER_NAME_MIN_LEN} characters."
    elif len(cleaned_name) > USER_NAME_MAX_LEN:
        errors["name"] = f"Name must be under {USER_NAME_MAX_LEN} characters."

    if not cleaned_email:
        errors["email"] = "Email cannot be blank."
    elif not EMAIL_PATTERN.fullmatch(cleaned_email):
        errors["email"] = "Enter a valid email address."

    digit_count = sum(character.isdigit() for character in cleaned_phone)

    if not cleaned_phone:
        errors["phone"] = "Phone number cannot be blank."
    elif not PHONE_PATTERN.fullmatch(cleaned_phone):
        errors["phone"] = "Phone number contains invalid characters."
    elif digit_count < 7 or digit_count > 15:
        errors["phone"] = "Phone number must contain between 7 and 15 digits."

    if not password:
        errors["password"] = "Password cannot be blank."
    elif len(password) < PASSWORD_MIN_LEN:
        errors["password"] = f"Password must be at least {PASSWORD_MIN_LEN} characters."
    elif len(password) > PASSWORD_MAX_LEN:
        errors["password"] = f"Password must not exceed {PASSWORD_MAX_LEN} characters."
    elif not any(character.isalpha() for character in password):
        errors["password"] = "Password must contain at least one letter."
    elif not any(character.isdigit() for character in password):
        errors["password"] = "Password must contain at least one number."

    values = {
        "name": cleaned_name,
        "email": cleaned_email,
        "phone": cleaned_phone,
    }

    return errors, values


def find_user_by_email(
    email: str,
    session: Session,
) -> User | None:
    """Find an existing user using a normalized email address."""

    normalized_email = normalize_email(email)

    return session.exec(select(User).where(User.email == normalized_email)).first()


def register_attendee_record(
    name: str,
    email: str,
    phone: str,
    password: str,
    session: Session,
) -> User:
    """Validate and save a new attendee account."""

    errors, values = validate_attendee_registration(
        name,
        email,
        phone,
        password,
    )

    if errors:
        raise HTTPException(
            status_code=422,
            detail=errors,
        )

    if find_user_by_email(values["email"], session) is not None:
        raise HTTPException(
            status_code=409,
            detail={"email": "An account with this email already exists."},
        )

    user = User(
        name=values["name"],
        email=values["email"],
        phone=values["phone"],
        role="attendee",
        password_hash=password_hash.hash(password),
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    return user


# --- SCRUM-203: Concert field validation (shared by the API and the HTML form) ---
CONCERT_TEXT_FIELDS = ("title", "venue", "organiser")
CONCERT_TEXT_MIN_LEN = 2
CONCERT_TEXT_MAX_LEN = 200


def validate_concert_fields(title: str, date: str, venue: str, organiser: str) -> dict[str, str]:
    """
    Validate organiser-submitted concert fields.

    Returns a dict of field name -> error message. An empty dict means the
    input is valid. Used by both the JSON API and the HTML form so the two
    paths can never enforce different rules.
    """
    errors: dict[str, str] = {}
    values = {"title": title, "venue": venue, "organiser": organiser}

    for field_name in CONCERT_TEXT_FIELDS:
        trimmed = values[field_name].strip()
        if not trimmed:
            errors[field_name] = f"{field_name.capitalize()} cannot be blank."
        elif len(trimmed) < CONCERT_TEXT_MIN_LEN:
            errors[field_name] = (
                f"{field_name.capitalize()} must be at least {CONCERT_TEXT_MIN_LEN} characters."
            )
        elif len(trimmed) > CONCERT_TEXT_MAX_LEN:
            errors[field_name] = (
                f"{field_name.capitalize()} must be under {CONCERT_TEXT_MAX_LEN} characters."
            )

    try:
        parsed_date = date_cls.fromisoformat(date.strip())
    except ValueError:
        errors["date"] = "Enter a valid date (YYYY-MM-DD)."
    else:
        if parsed_date < date_cls.today():
            errors["date"] = "Date cannot be in the past."

    return errors


# --- SCRUM-204: Ticket and booking validation ---

TICKET_CATEGORY_MIN_LEN = 2
TICKET_CATEGORY_MAX_LEN = 100
ATTENDEE_NAME_MIN_LEN = 2
ATTENDEE_NAME_MAX_LEN = 100


def _parse_price(value: str | int | float) -> tuple[float | None, str | None]:
    """Parse and validate a ticket price."""

    raw_value = str(value).strip()

    try:
        parsed_price = Decimal(raw_value)
    except InvalidOperation:
        return None, "Enter a valid ticket price."

    if not parsed_price.is_finite():
        return None, "Enter a valid ticket price."

    if parsed_price < 0:
        return None, "Ticket price cannot be negative."

    return float(parsed_price), None


def _parse_whole_quantity(
    value: str | int | float,
    *,
    field_label: str,
) -> tuple[int | None, str | None]:
    """Parse a strictly positive whole-number quantity."""

    raw_value = str(value).strip()

    if not raw_value:
        return None, f"{field_label} is required."

    try:
        parsed_quantity = Decimal(raw_value)
    except InvalidOperation:
        return None, f"{field_label} must be a whole number."

    if not parsed_quantity.is_finite():
        return None, f"{field_label} must be a whole number."

    if parsed_quantity != parsed_quantity.to_integral_value():
        return None, f"{field_label} must be a whole number."

    quantity = int(parsed_quantity)

    if quantity <= 0:
        return None, f"{field_label} must be at least 1."

    return quantity, None


def validate_ticket_fields(
    category: str,
    price: str | int | float,
    quantity: str | int | float,
) -> tuple[dict[str, str], str, float | None, int | None]:
    """Validate and clean ticket-category fields."""

    errors: dict[str, str] = {}
    cleaned_category = category.strip()

    if not cleaned_category:
        errors["category"] = "Ticket category cannot be blank."
    elif len(cleaned_category) < TICKET_CATEGORY_MIN_LEN:
        errors["category"] = (
            f"Ticket category must be at least {TICKET_CATEGORY_MIN_LEN} characters."
        )
    elif len(cleaned_category) > TICKET_CATEGORY_MAX_LEN:
        errors["category"] = f"Ticket category must be under {TICKET_CATEGORY_MAX_LEN} characters."

    parsed_price, price_error = _parse_price(price)
    if price_error is not None:
        errors["price"] = price_error

    parsed_quantity, quantity_error = _parse_whole_quantity(
        quantity,
        field_label="Ticket quantity",
    )
    if quantity_error is not None:
        errors["quantity"] = quantity_error

    return errors, cleaned_category, parsed_price, parsed_quantity


def validate_booking_fields(
    attendee: str,
    quantity: str | int | float,
    remaining: int,
) -> tuple[dict[str, str], str, int | None]:
    """Validate attendee name, booking quantity, and ticket availability."""

    errors: dict[str, str] = {}
    cleaned_attendee = attendee.strip()

    if not cleaned_attendee:
        errors["attendee"] = "Attendee name cannot be blank."
    elif len(cleaned_attendee) < ATTENDEE_NAME_MIN_LEN:
        errors["attendee"] = f"Attendee name must be at least {ATTENDEE_NAME_MIN_LEN} characters."
    elif len(cleaned_attendee) > ATTENDEE_NAME_MAX_LEN:
        errors["attendee"] = f"Attendee name must be under {ATTENDEE_NAME_MAX_LEN} characters."

    parsed_quantity, quantity_error = _parse_whole_quantity(
        quantity,
        field_label="Booking quantity",
    )

    if quantity_error is not None:
        errors["quantity"] = quantity_error
    elif parsed_quantity is not None and parsed_quantity > remaining:
        errors["quantity"] = f"Only {remaining} ticket(s) remaining."

    return errors, cleaned_attendee, parsed_quantity


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create database tables on startup."""
    init_db()
    yield


app = FastAPI(
    title="Concert Registration and Ticketing Portal",
    version="0.1.0",
    lifespan=lifespan,
)

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")

# Short codes carried in redirect query strings (e.g. ?error=oversold) so the
# URL stays clean; the human-readable wording lives here in one place.
BOOKING_ERROR_CODES = {400: "bad_quantity", 404: "not_found", 409: "oversold"}
BOOKING_ERROR_MESSAGES = {
    "bad_quantity": "Quantity must be at least 1.",
    "blank_attendee": "Attendee name cannot be blank.",
    "invalid_attendee": "Enter a valid attendee name.",
    "not_found": "That ticket could not be found.",
    "oversold": "Not enough tickets left for that quantity.",
    "concert_missing": "That concert could not be found.",
}

CANCELLATION_MESSAGES = {
    "cancelled": "Booking cancelled successfully. The reserved tickets are available again.",
    "not_pending": "Only bookings that are still pending payment can be cancelled.",
    "already_cancelled": "This booking has already been cancelled.",
}


def _error_message(code: str | None) -> str | None:
    """Map a short error code from the query string to display text."""
    if code is None:
        return None
    return BOOKING_ERROR_MESSAGES.get(code, "Something went wrong with that booking.")


def _cancellation_message(code: str | None) -> str | None:
    """Map a cancellation result code to a readable message."""

    if code is None:
        return None

    return CANCELLATION_MESSAGES.get(
        code,
        "Something went wrong while cancelling the booking.",
    )


@app.get("/health")
def health() -> dict:
    """Simple health check endpoint used by tests and monitoring."""
    return {"status": "ok"}


# --- Attendee API ---
@app.post(
    "/users/attendees",
    response_model=UserRead,
    status_code=201,
)
def register_attendee(
    data: AttendeeCreate,
    session: Session = Depends(get_session),
) -> User:
    """US01 — Register a new attendee account."""

    return register_attendee_record(
        data.name,
        data.email,
        data.phone,
        data.password,
        session,
    )


@app.get("/register/attendee", response_class=HTMLResponse)
def attendee_registration_form(
    request: Request,
    registered: bool = False,
) -> HTMLResponse:
    """Show the attendee-registration form."""

    return templates.TemplateResponse(
        request,
        "attendee_register.html",
        {
            "errors": {},
            "values": {},
            "registered": registered,
        },
    )


@app.post("/register/attendee", response_model=None)
def attendee_registration_submit(
    request: Request,
    name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    password: str = Form(""),
    session: Session = Depends(get_session),
) -> RedirectResponse | HTMLResponse:
    """Validate and process attendee registration."""

    errors, values = validate_attendee_registration(
        name,
        email,
        phone,
        password,
    )

    if not errors and find_user_by_email(values["email"], session) is not None:
        errors["email"] = "An account with this email already exists."

    if errors:
        return templates.TemplateResponse(
            request,
            "attendee_register.html",
            {
                "errors": errors,
                "values": values,
                "registered": False,
            },
            status_code=422,
        )

    register_attendee_record(
        values["name"],
        values["email"],
        values["phone"],
        password,
        session,
    )

    return RedirectResponse(
        url="/register/attendee?registered=true",
        status_code=303,
    )


# --- JSON API ---
@app.post("/concerts", response_model=ConcertRead, status_code=201)
def create_concert(
    data: ConcertCreate,
    session: Session = Depends(get_session),
) -> Concert:
    """US07 — Organiser creates a concert event."""
    errors = validate_concert_fields(data.title, data.date, data.venue, data.organiser)
    if errors:
        raise HTTPException(status_code=422, detail=errors)
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


# --- Web UI ---
@app.get("/", response_class=HTMLResponse)
def concerts_page(
    request: Request,
    error: str | None = None,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Show all concerts."""
    concerts = session.exec(select(Concert)).all()
    return templates.TemplateResponse(
        request,
        "concerts.html",
        {"concerts": concerts, "error": _error_message(error)},
    )


@app.get("/concerts/new", response_class=HTMLResponse)
def concert_new_form(request: Request) -> HTMLResponse:
    """Show the create-concert form."""
    return templates.TemplateResponse(request, "concert_new.html", {"errors": {}, "values": {}})


@app.post("/concerts/new", response_model=None)
def concert_new_submit(
    request: Request,
    title: str = Form(...),
    date: str = Form(...),
    venue: str = Form(...),
    organiser: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse | HTMLResponse:
    """Handle the HTML form submission. Re-shows the form with field-specific
    errors and the entered values preserved if validation fails; otherwise
    redirects to the new concert's page."""
    errors = validate_concert_fields(title, date, venue, organiser)
    if errors:
        return templates.TemplateResponse(
            request,
            "concert_new.html",
            {
                "errors": errors,
                "values": {"title": title, "date": date, "venue": venue, "organiser": organiser},
            },
            status_code=422,
        )
    concert = Concert(
        title=title.strip(), date=date.strip(), venue=venue.strip(), organiser=organiser.strip()
    )
    session.add(concert)
    session.commit()
    session.refresh(concert)
    return RedirectResponse(url=f"/concerts/{concert.id}", status_code=303)


@app.post("/tickets", response_model=TicketRead, status_code=201)
def create_ticket(
    data: TicketCreate,
    session: Session = Depends(get_session),
) -> Ticket:
    """US15/16/17 — Create a validated ticket category."""

    concert = session.get(Concert, data.concert_id)
    if concert is None:
        raise HTTPException(status_code=404, detail="Concert not found")

    errors, category, price, quantity = validate_ticket_fields(
        data.category,
        data.price,
        data.quantity,
    )

    if errors:
        raise HTTPException(status_code=422, detail=errors)

    if price is None or quantity is None:
        raise HTTPException(status_code=422, detail="Invalid ticket data")

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


@app.get("/concerts/{concert_id}/tickets", response_model=list[TicketRead])
def list_tickets(
    concert_id: int,
    session: Session = Depends(get_session),
) -> list[Ticket]:
    """List all ticket categories for a concert."""
    tickets = session.exec(select(Ticket).where(Ticket.concert_id == concert_id)).all()
    return list(tickets)


@app.get("/concerts/{concert_id}/tickets/new", response_class=HTMLResponse)
def ticket_new_form(
    concert_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Show the add-ticket-category form for a concert."""

    concert = session.get(Concert, concert_id)
    if concert is None:
        raise HTTPException(status_code=404, detail="Concert not found")

    return templates.TemplateResponse(
        request,
        "ticket_new.html",
        {
            "concert": concert,
            "errors": {},
            "values": {},
        },
    )


@app.post("/concerts/{concert_id}/tickets/new", response_model=None)
def ticket_new_submit(
    concert_id: int,
    request: Request,
    category: str = Form(...),
    price: str = Form(...),
    quantity: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse | HTMLResponse:
    """Validate and process the HTML ticket form."""

    concert = session.get(Concert, concert_id)
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
        raise HTTPException(status_code=422, detail="Invalid ticket data")

    ticket = Ticket(
        concert_id=concert_id,
        category=cleaned_category,
        price=parsed_price,
        quantity=parsed_quantity,
    )

    session.add(ticket)
    session.commit()

    return RedirectResponse(
        url=f"/concerts/{concert_id}",
        status_code=303,
    )


@app.post("/bookings", response_model=BookingRead, status_code=201)
def create_booking(
    data: BookingCreate,
    session: Session = Depends(get_session),
) -> Booking:
    """Create a validated booking while preventing overselling."""

    ticket = session.get(Ticket, data.ticket_id)

    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found",
        )

    remaining = max(ticket.quantity - ticket.sold, 0)

    errors, attendee, quantity = validate_booking_fields(
        data.attendee,
        data.quantity,
        remaining,
    )

    if errors:
        quantity_error = errors.get("quantity", "")
        attendee_error = errors.get("attendee", "")

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
                detail={"quantity": quantity_error},
            )

        if attendee_error:
            raise HTTPException(
                status_code=422,
                detail={"attendee": attendee_error},
            )

        raise HTTPException(
            status_code=422,
            detail=errors,
        )

    if quantity is None:
        raise HTTPException(
            status_code=422,
            detail={"quantity": "Invalid booking quantity"},
        )

    new_sold_quantity = ticket.sold + quantity

    if new_sold_quantity > ticket.quantity:
        raise HTTPException(
            status_code=409,
            detail={
                "quantity": "Not enough tickets remaining.",
                "remaining": remaining,
            },
        )

    booking = Booking(
        ticket_id=data.ticket_id,
        attendee=attendee,
        quantity=quantity,
    )

    ticket.sold = new_sold_quantity

    session.add(booking)
    session.add(ticket)
    session.commit()
    session.refresh(booking)

    return booking


def cancel_booking_record(
    booking_id: int,
    session: Session,
) -> Booking:
    """Cancel a pending booking and restore its reserved ticket quantity."""

    booking = session.get(Booking, booking_id)

    if booking is None:
        raise HTTPException(
            status_code=404,
            detail="Booking not found",
        )

    if booking.status == "cancelled":
        raise HTTPException(
            status_code=409,
            detail="This booking has already been cancelled.",
        )

    if booking.status != "pending_payment":
        raise HTTPException(
            status_code=409,
            detail="Only bookings that are still pending payment can be cancelled.",
        )

    ticket = session.get(Ticket, booking.ticket_id)

    if ticket is None:
        raise HTTPException(
            status_code=404,
            detail="Ticket not found",
        )

    ticket.sold = max(ticket.sold - booking.quantity, 0)
    booking.status = "cancelled"

    session.add(ticket)
    session.add(booking)
    session.commit()
    session.refresh(booking)

    return booking


@app.post(
    "/bookings/{booking_id}/cancel",
    response_model=BookingRead,
)
def cancel_booking(
    booking_id: int,
    session: Session = Depends(get_session),
) -> Booking:
    """US23 — Cancel a booking that is still pending payment."""

    return cancel_booking_record(booking_id, session)


UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"


@app.get("/concerts/{concert_id}", response_class=HTMLResponse)
def concert_detail_page(
    concert_id: int,
    request: Request,
    error: str | None = None,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """US14 — Attendee views concert details and ticket options."""
    concert = session.get(Concert, concert_id)
    if concert is None:
        raise HTTPException(status_code=404, detail="Concert not found")

    tickets = session.exec(select(Ticket).where(Ticket.concert_id == concert_id)).all()
    return templates.TemplateResponse(
        request,
        "concert_detail.html",
        {"concert": concert, "tickets": list(tickets), "error": _error_message(error)},
    )


@app.post("/bookings/new")
def booking_new_submit(
    ticket_id: int = Form(...),
    attendee: str = Form(...),
    quantity: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Validate and process the HTML booking form."""

    ticket = session.get(Ticket, ticket_id)

    if ticket is None:
        return RedirectResponse(
            url="/?error=not_found",
            status_code=303,
        )

    remaining = max(ticket.quantity - ticket.sold, 0)

    errors, cleaned_attendee, parsed_quantity = validate_booking_fields(
        attendee,
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
            url=f"/concerts/{ticket.concert_id}?error={error_code}",
            status_code=303,
        )

    if parsed_quantity is None:
        return RedirectResponse(
            url=f"/concerts/{ticket.concert_id}?error=bad_quantity",
            status_code=303,
        )

    try:
        booking = create_booking(
            BookingCreate(
                ticket_id=ticket_id,
                attendee=cleaned_attendee,
                quantity=parsed_quantity,
            ),
            session,
        )
    except HTTPException as exc:
        error_code = BOOKING_ERROR_CODES.get(exc.status_code, "bad_quantity")

        return RedirectResponse(
            url=f"/concerts/{ticket.concert_id}?error={error_code}",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/bookings/{booking.id}",
        status_code=303,
    )


@app.get("/bookings/{booking_id}", response_class=HTMLResponse)
def booking_detail_page(
    booking_id: int,
    request: Request,
    message: str | None = None,
    error: str | None = None,
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
        },
    )


@app.post("/bookings/{booking_id}/cancel/form")
def cancel_booking_submit(
    booking_id: int,
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Process booking cancellation from the booking detail page."""

    try:
        cancel_booking_record(booking_id, session)
    except HTTPException as exc:
        if exc.status_code == 404:
            raise

        detail = str(exc.detail)

        if "already been cancelled" in detail:
            error_code = "already_cancelled"
        else:
            error_code = "not_pending"

        return RedirectResponse(
            url=f"/bookings/{booking_id}?error={error_code}",
            status_code=303,
        )

    return RedirectResponse(
        url=f"/bookings/{booking_id}?message=cancelled",
        status_code=303,
    )


@app.post("/bookings/{booking_id}/payment-proof")
def upload_payment_proof(
    booking_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """US24 — Attendee uploads payment proof for a booking."""
    booking = session.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    if booking.status == "cancelled":
        raise HTTPException(
            status_code=409,
            detail="Cancelled bookings cannot upload payment proof",
        )

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"booking_{booking_id}_{file.filename}"
    (UPLOAD_DIR / filename).write_bytes(file.file.read())

    proof = PaymentProof(booking_id=booking_id, filename=filename)
    booking.status = "payment_uploaded"

    session.add(proof)
    session.add(booking)
    session.commit()

    return RedirectResponse(url=f"/bookings/{booking_id}", status_code=303)
