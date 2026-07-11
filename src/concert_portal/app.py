from itertools import count

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Concert Registration and Ticketing Portal", version="0.1.0")


class ConcertCreate(BaseModel):
    title: str
    date: str
    venue: str
    organiser: str


class Concert(ConcertCreate):
    id: int


# --- In-memory store (fine for a teaching/demo app) ---
concerts: dict[int, Concert] = {}
_concert_ids = count(1)


@app.get("/health")
def health() -> dict:
    """Simple health check endpoint used by tests and monitoring."""
    return {"status": "ok"}


@app.post("/concerts", response_model=Concert, status_code=201)
def create_concert(data: ConcertCreate) -> Concert:
    """US07 — Organiser creates a concert event."""
    concert = Concert(id=next(_concert_ids), **data.model_dump())
    concerts[concert.id] = concert
    return concert
