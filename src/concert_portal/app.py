from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from sqlmodel import Session

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


@app.get("/health")
def health() -> dict:
    """Simple health check endpoint used by tests and monitoring."""
    return {"status": "ok"}


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
