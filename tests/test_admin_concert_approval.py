from fastapi.testclient import TestClient
from sqlmodel import Session

from concert_portal.models import (
    Concert,
    ConcertApproval,
    Ticket,
    TicketSalesPeriod,
    User,
)
from concert_portal.security import password_hash


def _create_user(
    session: Session,
    *,
    email: str,
    role: str,
) -> User:
    """Create a user for admin-access tests."""

    user = User(
        name=f"Test {role.title()}",
        email=email,
        phone="012-3456789",
        role=role,
        password_hash=password_hash.hash(
            "Password123",
        ),
    )

    session.add(
        user,
    )
    session.commit()
    session.refresh(
        user,
    )

    return user


def _login(
    client: TestClient,
    *,
    email: str,
) -> None:
    """Login using the standard test password."""

    response = client.post(
        "/login",
        data={
            "email": email,
            "password": "Password123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303


def _create_pending_concert(
    session: Session,
) -> tuple[Concert, ConcertApproval]:
    """Create a concert awaiting administrator approval."""

    concert = Concert(
        title="Admin Approval Concert",
        date="2030-08-01",
        venue="National Stadium",
        organiser="Test Events",
    )

    session.add(
        concert,
    )
    session.commit()
    session.refresh(
        concert,
    )

    assert concert.id is not None

    approval = ConcertApproval(
        concert_id=concert.id,
        status="pending",
    )

    session.add(
        approval,
    )
    session.commit()
    session.refresh(
        approval,
    )

    return concert, approval


def test_admin_concert_page_requires_login(
    client: TestClient,
) -> None:
    """Unauthenticated users cannot access concert approval."""

    response = client.get(
        "/admin/concerts",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_non_admin_cannot_access_concert_approval(
    client: TestClient,
    session: Session,
) -> None:
    """Attendees cannot access administrator concert review."""

    _create_user(
        session,
        email="attendee@example.com",
        role="attendee",
    )

    _login(
        client,
        email="attendee@example.com",
    )

    response = client.get(
        "/admin/concerts",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_admin_can_view_pending_concerts(
    client: TestClient,
    session: Session,
) -> None:
    """Pending concerts appear in the administrator list."""

    _create_user(
        session,
        email="admin@example.com",
        role="admin",
    )

    concert, _approval = _create_pending_concert(
        session,
    )

    assert concert.id is not None

    _login(
        client,
        email="admin@example.com",
    )

    response = client.get(
        "/admin/concerts",
    )

    assert response.status_code == 200
    assert "Concert Approval" in response.text
    assert "Admin Approval Concert" in response.text
    assert "National Stadium" in response.text
    assert "Test Events" in response.text
    assert f"/admin/concerts/{concert.id}" in response.text


def test_approved_concert_not_in_pending_list(
    client: TestClient,
    session: Session,
) -> None:
    """Already approved concerts disappear from the pending list."""

    _create_user(
        session,
        email="admin@example.com",
        role="admin",
    )

    concert, approval = _create_pending_concert(
        session,
    )

    approval.status = "approved"

    session.add(
        approval,
    )
    session.commit()

    _login(
        client,
        email="admin@example.com",
    )

    response = client.get(
        "/admin/concerts",
    )

    assert response.status_code == 200
    assert "No pending concerts" in response.text
    assert concert.title not in response.text


def test_admin_can_view_concert_review_details(
    client: TestClient,
    session: Session,
) -> None:
    """Administrator can inspect concert and ticket details."""

    _create_user(
        session,
        email="admin@example.com",
        role="admin",
    )

    concert, _approval = _create_pending_concert(
        session,
    )

    assert concert.id is not None

    sales_period = TicketSalesPeriod(
        concert_id=concert.id,
        sales_start="2030-01-01",
        sales_end="2030-07-31",
    )

    ticket = Ticket(
        concert_id=concert.id,
        category="VIP",
        price=250.00,
        quantity=100,
    )

    session.add(
        sales_period,
    )
    session.add(
        ticket,
    )
    session.commit()

    _login(
        client,
        email="admin@example.com",
    )

    response = client.get(
        f"/admin/concerts/{concert.id}",
    )

    assert response.status_code == 200

    assert "Admin Approval Concert" in response.text
    assert "National Stadium" in response.text
    assert "Test Events" in response.text
    assert "2030-01-01" in response.text
    assert "2030-07-31" in response.text
    assert "VIP" in response.text
    assert "250.00" in response.text
    assert "Approve concert" in response.text
    assert "Reject concert" in response.text


def test_admin_can_approve_concert(
    client: TestClient,
    session: Session,
) -> None:
    """Approving changes the concert approval status."""

    _create_user(
        session,
        email="admin@example.com",
        role="admin",
    )

    concert, approval = _create_pending_concert(
        session,
    )

    assert concert.id is not None

    _login(
        client,
        email="admin@example.com",
    )

    response = client.post(
        f"/admin/concerts/{concert.id}/approve",
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert response.headers["location"].startswith(
        "/admin/concerts?message=",
    )

    session.refresh(
        approval,
    )

    assert approval.status == "approved"


def test_approved_concert_shows_approved_status(
    client: TestClient,
    session: Session,
) -> None:
    """The normal concert page reflects administrator approval."""

    _create_user(
        session,
        email="admin@example.com",
        role="admin",
    )

    concert, approval = _create_pending_concert(
        session,
    )

    assert concert.id is not None

    _login(
        client,
        email="admin@example.com",
    )

    response = client.post(
        f"/admin/concerts/{concert.id}/approve",
        follow_redirects=False,
    )

    assert response.status_code == 303

    session.refresh(
        approval,
    )

    page = client.get(
        f"/concerts/{concert.id}",
    )

    assert page.status_code == 200
    assert "Approved" in page.text


def test_admin_can_reject_concert(
    client: TestClient,
    session: Session,
) -> None:
    """Rejecting changes the concert status to rejected."""

    _create_user(
        session,
        email="admin@example.com",
        role="admin",
    )

    concert, approval = _create_pending_concert(
        session,
    )

    assert concert.id is not None

    _login(
        client,
        email="admin@example.com",
    )

    response = client.post(
        f"/admin/concerts/{concert.id}/reject",
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert response.headers["location"].startswith(
        "/admin/concerts?message=",
    )

    session.refresh(
        approval,
    )

    assert approval.status == "rejected"


def test_rejected_concert_becomes_editable(
    client: TestClient,
    session: Session,
) -> None:
    """Rejected concerts can be edited and resubmitted."""

    _create_user(
        session,
        email="admin@example.com",
        role="admin",
    )

    concert, _approval = _create_pending_concert(
        session,
    )

    assert concert.id is not None

    _login(
        client,
        email="admin@example.com",
    )

    reject_response = client.post(
        f"/admin/concerts/{concert.id}/reject",
        follow_redirects=False,
    )

    assert reject_response.status_code == 303

    edit_response = client.get(
        f"/concerts/{concert.id}/edit",
        follow_redirects=False,
    )

    assert edit_response.status_code == 200


def test_non_admin_cannot_approve_concert(
    client: TestClient,
    session: Session,
) -> None:
    """Non-admin users cannot change approval status."""

    _create_user(
        session,
        email="attendee@example.com",
        role="attendee",
    )

    concert, approval = _create_pending_concert(
        session,
    )

    assert concert.id is not None

    _login(
        client,
        email="attendee@example.com",
    )

    response = client.post(
        f"/admin/concerts/{concert.id}/approve",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"

    session.refresh(
        approval,
    )

    assert approval.status == "pending"


def test_reviewed_concert_cannot_be_approved_again(
    client: TestClient,
    session: Session,
) -> None:
    """Only pending concerts may be approved."""

    _create_user(
        session,
        email="admin@example.com",
        role="admin",
    )

    concert, approval = _create_pending_concert(
        session,
    )

    assert concert.id is not None

    approval.status = "approved"

    session.add(
        approval,
    )
    session.commit()

    _login(
        client,
        email="admin@example.com",
    )

    response = client.post(
        f"/admin/concerts/{concert.id}/approve",
        follow_redirects=False,
    )

    assert response.status_code == 303

    assert response.headers["location"].startswith(
        "/admin/concerts?error=",
    )

    session.refresh(
        approval,
    )

    assert approval.status == "approved"


def test_missing_concert_approval_returns_404(
    client: TestClient,
    session: Session,
) -> None:
    """Missing approval requests return 404."""

    _create_user(
        session,
        email="admin@example.com",
        role="admin",
    )

    _login(
        client,
        email="admin@example.com",
    )

    response = client.post(
        "/admin/concerts/99999/approve",
        follow_redirects=False,
    )

    assert response.status_code == 404
