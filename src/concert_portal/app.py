from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from concert_portal.database import get_session, init_db
from concert_portal.models import Concert, ConcertCreate, ConcertRead


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
