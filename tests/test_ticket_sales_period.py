from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from concert_portal.models import (
    Booking,
    Concert,
    Ticket,
    TicketSalesPeriod,
)


def _create_concert(
    session: Session,
) -> Concert:
    """Create a concert for ticket-sales tests."""

    concert = Concert(
        title="Sales Period Concert",
        date="2030-08-01",
        venue="Test Stadium",
        organiser="Test Organiser",
    )

    session.add(
        concert,
    )
    session.commit()
    session.refresh(
        concert,
    )

    return concert


def _create_ticket(
    concert: Concert,
    session: Session,
) -> Ticket:
    """Create a ticket category for the concert."""

    assert concert.id is not None

    ticket = Ticket(
        concert_id=concert.id,
        category="Standard",
        price=100.00,
        quantity=20,
    )

    session.add(
        ticket,
    )
    session.commit()
    session.refresh(
        ticket,
    )

    return ticket


def test_sales_period_page_loads(
    client: TestClient,
    session: Session,
) -> None:
    """The organiser can open the sales-period form."""

    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    response = client.get(
        f"/concerts/{concert.id}/sales-period",
    )

    assert response.status_code == 200
    assert "Ticket Sales Period" in response.text
    assert 'name="sales_start"' in response.text
    assert 'name="sales_end"' in response.text


def test_missing_concert_sales_period_returns_404(
    client: TestClient,
) -> None:
    """A missing concert cannot have a sales period."""

    response = client.get(
        "/concerts/99999/sales-period",
    )

    assert response.status_code == 404


def test_sales_period_can_be_saved(
    client: TestClient,
    session: Session,
) -> None:
    """Valid start and end dates are stored."""

    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    response = client.post(
        f"/concerts/{concert.id}/sales-period",
        data={
            "sales_start": "2030-01-01",
            "sales_end": "2030-07-31",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert response.headers["location"] == (f"/concerts/{concert.id}" "/sales-period?updated=true")

    sales_period = session.exec(
        select(TicketSalesPeriod).where(
            TicketSalesPeriod.concert_id == concert.id,
        )
    ).first()

    assert sales_period is not None
    assert sales_period.sales_start == "2030-01-01"
    assert sales_period.sales_end == "2030-07-31"


def test_existing_sales_period_is_prefilled(
    client: TestClient,
    session: Session,
) -> None:
    """Stored dates are shown when reopening the form."""

    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    sales_period = TicketSalesPeriod(
        concert_id=concert.id,
        sales_start="2030-01-01",
        sales_end="2030-07-31",
    )

    session.add(
        sales_period,
    )
    session.commit()

    response = client.get(
        f"/concerts/{concert.id}/sales-period",
    )

    assert response.status_code == 200
    assert 'value="2030-01-01"' in response.text
    assert 'value="2030-07-31"' in response.text


def test_sales_period_can_be_updated(
    client: TestClient,
    session: Session,
) -> None:
    """Saving again updates the existing period."""

    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    sales_period = TicketSalesPeriod(
        concert_id=concert.id,
        sales_start="2030-01-01",
        sales_end="2030-06-01",
    )

    session.add(
        sales_period,
    )
    session.commit()

    response = client.post(
        f"/concerts/{concert.id}/sales-period",
        data={
            "sales_start": "2030-02-01",
            "sales_end": "2030-07-01",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    stored_periods = session.exec(
        select(TicketSalesPeriod).where(
            TicketSalesPeriod.concert_id == concert.id,
        )
    ).all()

    assert len(stored_periods) == 1
    assert stored_periods[0].sales_start == "2030-02-01"
    assert stored_periods[0].sales_end == "2030-07-01"


def test_blank_sales_dates_are_rejected(
    client: TestClient,
    session: Session,
) -> None:
    """Both ticket-sales dates are required."""

    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    response = client.post(
        f"/concerts/{concert.id}/sales-period",
        data={
            "sales_start": "",
            "sales_end": "",
        },
    )

    assert response.status_code == 422
    assert "Sales start date is required." in response.text
    assert "Sales end date is required." in response.text


def test_end_before_start_is_rejected(
    client: TestClient,
    session: Session,
) -> None:
    """The end date cannot be earlier than the start date."""

    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    response = client.post(
        f"/concerts/{concert.id}/sales-period",
        data={
            "sales_start": "2030-07-31",
            "sales_end": "2030-01-01",
        },
    )

    assert response.status_code == 422

    assert "Sales end date cannot be before " "the sales start date." in response.text

    sales_period = session.exec(
        select(TicketSalesPeriod).where(
            TicketSalesPeriod.concert_id == concert.id,
        )
    ).first()

    assert sales_period is None


def test_booking_allowed_during_sales_period(
    client: TestClient,
    session: Session,
) -> None:
    """Booking succeeds while today's date is inside the period."""

    concert = _create_concert(
        session,
    )

    ticket = _create_ticket(
        concert,
        session,
    )

    assert concert.id is not None
    assert ticket.id is not None

    today = date.today()

    sales_period = TicketSalesPeriod(
        concert_id=concert.id,
        sales_start=(today - timedelta(days=1)).isoformat(),
        sales_end=(today + timedelta(days=1)).isoformat(),
    )

    session.add(
        sales_period,
    )
    session.commit()

    response = client.post(
        "/bookings",
        json={
            "ticket_id": ticket.id,
            "attendee": "Alyssa",
            "quantity": 1,
        },
    )

    assert response.status_code == 201

    booking = session.exec(
        select(Booking).where(
            Booking.ticket_id == ticket.id,
        )
    ).first()

    assert booking is not None


def test_booking_blocked_before_sales_start(
    client: TestClient,
    session: Session,
) -> None:
    """Booking is rejected before ticket sales begin."""

    concert = _create_concert(
        session,
    )

    ticket = _create_ticket(
        concert,
        session,
    )

    assert concert.id is not None
    assert ticket.id is not None

    today = date.today()

    sales_period = TicketSalesPeriod(
        concert_id=concert.id,
        sales_start=(today + timedelta(days=2)).isoformat(),
        sales_end=(today + timedelta(days=5)).isoformat(),
    )

    session.add(
        sales_period,
    )
    session.commit()

    response = client.post(
        "/bookings",
        json={
            "ticket_id": ticket.id,
            "attendee": "Alyssa",
            "quantity": 1,
        },
    )

    assert response.status_code == 409

    assert "Ticket sales are not open" in response.text

    session.refresh(
        ticket,
    )

    assert ticket.sold == 0


def test_booking_blocked_after_sales_end(
    client: TestClient,
    session: Session,
) -> None:
    """Booking is rejected once ticket sales have ended."""

    concert = _create_concert(
        session,
    )

    ticket = _create_ticket(
        concert,
        session,
    )

    assert concert.id is not None
    assert ticket.id is not None

    today = date.today()

    sales_period = TicketSalesPeriod(
        concert_id=concert.id,
        sales_start=(today - timedelta(days=5)).isoformat(),
        sales_end=(today - timedelta(days=2)).isoformat(),
    )

    session.add(
        sales_period,
    )
    session.commit()

    response = client.post(
        "/bookings",
        json={
            "ticket_id": ticket.id,
            "attendee": "Alyssa",
            "quantity": 1,
        },
    )

    assert response.status_code == 409

    session.refresh(
        ticket,
    )

    assert ticket.sold == 0


def test_booking_page_disabled_before_sales_start(
    client: TestClient,
    session: Session,
) -> None:
    """The concert page disables booking before sales begin."""

    concert = _create_concert(
        session,
    )

    _create_ticket(
        concert,
        session,
    )

    assert concert.id is not None

    today = date.today()

    sales_period = TicketSalesPeriod(
        concert_id=concert.id,
        sales_start=(today + timedelta(days=2)).isoformat(),
        sales_end=(today + timedelta(days=5)).isoformat(),
    )

    session.add(
        sales_period,
    )
    session.commit()

    response = client.get(
        f"/concerts/{concert.id}",
    )

    assert response.status_code == 200
    assert "Ticket booking is not available yet." in response.text
    assert "Ticket sales closed" in response.text


def test_no_sales_period_preserves_existing_booking_behaviour(
    client: TestClient,
    session: Session,
) -> None:
    """Legacy concerts remain bookable until a period is configured."""

    concert = _create_concert(
        session,
    )

    ticket = _create_ticket(
        concert,
        session,
    )

    assert ticket.id is not None

    response = client.post(
        "/bookings",
        json={
            "ticket_id": ticket.id,
            "attendee": "Alyssa",
            "quantity": 1,
        },
    )

    assert response.status_code == 201
