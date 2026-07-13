from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from concert_portal.database import get_session, init_db
from concert_portal.models import (
    Booking,
    BookingCreate,
    BookingRead,
    Concert,
    ConcertCreate,
    ConcertRead,
    Ticket,
    TicketCreate,
    TicketRead,
    PaymentProof,
)


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


@app.get("/health")
def health() -> dict:
    """Simple health check endpoint used by tests and monitoring."""
    return {"status": "ok"}


# --- JSON API ---
@app.post("/concerts", response_model=ConcertRead, status_code=201)
def create_concert(
    data: ConcertCreate,
    session: Session = Depends(get_session),
) -> Concert:
    """US07 — Organiser creates a concert event."""
    concert = Concert(**data.model_dump())
    session.add(concert)
    session.commit()
    session.refresh(concert)
    return concert


# --- Web UI ---
@app.get("/", response_class=HTMLResponse)
def concerts_page(
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Show all concerts."""
    concerts = session.exec(select(Concert)).all()
    return templates.TemplateResponse(request, "concerts.html", {"concerts": concerts})


@app.get("/concerts/new", response_class=HTMLResponse)
def concert_new_form(request: Request) -> HTMLResponse:
    """Show the create-concert form."""
    return templates.TemplateResponse(request, "concert_new.html", {})


@app.post("/concerts/new")
def concert_new_submit(
    title: str = Form(...),
    date: str = Form(...),
    venue: str = Form(...),
    organiser: str = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Handle the HTML form submission, then redirect to the list."""
    concert = Concert(title=title, date=date, venue=venue, organiser=organiser)
    session.add(concert)
    session.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/tickets", response_model=TicketRead, status_code=201)
def create_ticket(
    data: TicketCreate,
    session: Session = Depends(get_session),
) -> Ticket:
    """US15/16/17 — Organiser creates a ticket category with price and quantity."""
    concert = session.get(Concert, data.concert_id)
    if concert is None:
        raise HTTPException(status_code=404, detail="Concert not found")

    ticket = Ticket(**data.model_dump())
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


@app.post("/bookings", response_model=BookingRead, status_code=201)
def create_booking(
    data: BookingCreate,
    session: Session = Depends(get_session),
) -> Booking:
    """US20/21/19 — Attendee selects tickets and creates a booking.

    Rejects requests for a non-existent ticket, a non-positive quantity,
    or more tickets than remain available (prevents overselling).
    """
    # US20 — the selected ticket must exist
    ticket = session.get(Ticket, data.ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # US20 — quantity must be sensible
    if data.quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be at least 1")

    # US19 — prevent overselling
    remaining = ticket.quantity - ticket.sold
    if data.quantity > remaining:
        raise HTTPException(
            status_code=409,
            detail=f"Only {remaining} ticket(s) remaining",
        )

    # US21 — record the booking and reserve the tickets in one transaction
    booking = Booking(**data.model_dump())
    ticket.sold += data.quantity

    session.add(booking)
    session.add(ticket)
    session.commit()
    session.refresh(booking)
    return booking


UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"


@app.get("/concerts/{concert_id}", response_class=HTMLResponse)
def concert_detail_page(
    concert_id: int,
    request: Request,
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
        {"concert": concert, "tickets": list(tickets)},
    )


@app.post("/bookings/new")
def booking_new_submit(
    ticket_id: int = Form(...),
    attendee: str = Form(...),
    quantity: int = Form(...),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    """Handle the booking form, reusing the same rules as the API."""
    booking = create_booking(
        BookingCreate(ticket_id=ticket_id, attendee=attendee, quantity=quantity),
        session,
    )
    return RedirectResponse(url=f"/bookings/{booking.id}", status_code=303)


@app.get("/bookings/{booking_id}", response_class=HTMLResponse)
def booking_detail_page(
    booking_id: int,
    request: Request,
    session: Session = Depends(get_session),
) -> HTMLResponse:
    """Show a booking and its payment proof status."""
    booking = session.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")

    proof = session.exec(select(PaymentProof).where(PaymentProof.booking_id == booking_id)).first()
    return templates.TemplateResponse(
        request,
        "booking_detail.html",
        {"booking": booking, "proof": proof},
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

    UPLOAD_DIR.mkdir(exist_ok=True)
    filename = f"booking_{booking_id}_{file.filename}"
    (UPLOAD_DIR / filename).write_bytes(file.file.read())

    proof = PaymentProof(booking_id=booking_id, filename=filename)
    booking.status = "payment_uploaded"

    session.add(proof)
    session.add(booking)
    session.commit()

    return RedirectResponse(url=f"/bookings/{booking_id}", status_code=303)
