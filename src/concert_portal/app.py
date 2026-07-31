from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from concert_portal.database import init_db
from concert_portal.routers import admin_payments
from concert_portal.routers.auth import router as auth_router
from concert_portal.routers.bookings import router as bookings_router
from concert_portal.routers.concerts import router as concerts_router
from concert_portal.routers.dashboards import router as dashboards_router
from concert_portal.routers.payments import router as payments_router
from concert_portal.routers.registrations import router as registrations_router
from concert_portal.security import SESSION_SECRET_KEY
from concert_portal.web import STATIC_DIR


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

app.add_middleware(
    SessionMiddleware,
    secret_key=SESSION_SECRET_KEY,
    session_cookie="concert_portal_session",
    same_site="lax",
    https_only=False,
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

app.include_router(registrations_router)
app.include_router(auth_router)
app.include_router(dashboards_router)
app.include_router(concerts_router)
app.include_router(bookings_router)
app.include_router(payments_router)
app.include_router(admin_payments.router)


@app.get("/health")
def health() -> dict[str, str]:
    """Simple health check endpoint used by tests and monitoring."""
    return {"status": "ok"}
