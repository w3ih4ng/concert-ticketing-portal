from datetime import date

from fastapi import HTTPException
from sqlmodel import Session, select

from concert_portal.models import Concert, TicketSalesPeriod


def get_ticket_sales_period(
    concert_id: int,
    session: Session,
) -> TicketSalesPeriod | None:
    """Return the configured ticket sales period for a concert."""

    return session.exec(
        select(TicketSalesPeriod).where(
            TicketSalesPeriod.concert_id == concert_id,
        )
    ).first()


def validate_ticket_sales_period(
    sales_start: str,
    sales_end: str,
) -> dict[str, str]:
    """Validate ticket sales start and end dates."""

    errors: dict[str, str] = {}

    cleaned_start = sales_start.strip()
    cleaned_end = sales_end.strip()

    start_date: date | None = None
    end_date: date | None = None

    if not cleaned_start:
        errors["sales_start"] = "Sales start date is required."
    else:
        try:
            start_date = date.fromisoformat(
                cleaned_start,
            )
        except ValueError:
            errors["sales_start"] = "Enter a valid sales start date."

    if not cleaned_end:
        errors["sales_end"] = "Sales end date is required."
    else:
        try:
            end_date = date.fromisoformat(
                cleaned_end,
            )
        except ValueError:
            errors["sales_end"] = "Enter a valid sales end date."

    if start_date is not None and end_date is not None and start_date > end_date:
        errors["sales_end"] = "Sales end date cannot be before " "the sales start date."

    return errors


def save_ticket_sales_period(
    concert_id: int,
    sales_start: str,
    sales_end: str,
    session: Session,
) -> TicketSalesPeriod:
    """Create or update a concert ticket sales period."""

    concert = session.get(
        Concert,
        concert_id,
    )

    if concert is None:
        raise HTTPException(
            status_code=404,
            detail="Concert not found",
        )

    errors = validate_ticket_sales_period(
        sales_start,
        sales_end,
    )

    if errors:
        raise HTTPException(
            status_code=422,
            detail=errors,
        )

    existing = get_ticket_sales_period(
        concert_id,
        session,
    )

    if existing is None:
        sales_period = TicketSalesPeriod(
            concert_id=concert_id,
            sales_start=sales_start.strip(),
            sales_end=sales_end.strip(),
        )

        session.add(
            sales_period,
        )
        session.commit()
        session.refresh(
            sales_period,
        )

        return sales_period

    existing.sales_start = sales_start.strip()
    existing.sales_end = sales_end.strip()

    session.add(
        existing,
    )
    session.commit()
    session.refresh(
        existing,
    )

    return existing


def is_ticket_sales_open(
    concert_id: int,
    session: Session,
    *,
    current_date: date | None = None,
) -> bool:
    """Return whether tickets may currently be booked."""

    sales_period = get_ticket_sales_period(
        concert_id,
        session,
    )

    if sales_period is None:
        return True

    today = current_date or date.today()

    try:
        start_date = date.fromisoformat(
            sales_period.sales_start,
        )
        end_date = date.fromisoformat(
            sales_period.sales_end,
        )
    except ValueError:
        return False

    return start_date <= today <= end_date


def get_ticket_sales_status(
    concert_id: int,
    session: Session,
    *,
    current_date: date | None = None,
) -> str:
    """Return a readable ticket-sales status."""

    sales_period = get_ticket_sales_period(
        concert_id,
        session,
    )

    if sales_period is None:
        return "not_configured"

    today = current_date or date.today()

    try:
        start_date = date.fromisoformat(
            sales_period.sales_start,
        )
        end_date = date.fromisoformat(
            sales_period.sales_end,
        )
    except ValueError:
        return "closed"

    if today < start_date:
        return "not_started"

    if today > end_date:
        return "ended"

    return "open"
