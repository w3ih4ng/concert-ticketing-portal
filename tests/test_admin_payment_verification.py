from pathlib import Path

from fastapi.testclient import TestClient
from pwdlib import PasswordHash
from sqlmodel import Session

from concert_portal.models import (
    Booking,
    Concert,
    PaymentProof,
    Ticket,
    User,
)
from concert_portal.web import UPLOAD_DIR

password_hash = PasswordHash.recommended()

PNG_CONTENT = b"\x89PNG\r\n\x1a\n" b"admin payment review test"


def _create_user(
    session: Session,
    *,
    email: str,
    role: str,
) -> User:
    user = User(
        name=f"Test {role.title()}",
        email=email,
        phone="012-3456789",
        role=role,
        password_hash=password_hash.hash("Password123"),
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    return user


def _login(
    client: TestClient,
    *,
    email: str,
) -> None:
    response = client.post(
        "/login",
        data={
            "email": email,
            "password": "Password123",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303


def _create_payment_uploaded_booking(
    session: Session,
) -> tuple[Booking, PaymentProof, Path]:
    concert = Concert(
        title="Admin Review Concert",
        date="2027-12-20",
        venue="National Stadium",
        organiser="Live Events",
    )

    session.add(concert)
    session.commit()
    session.refresh(concert)

    assert concert.id is not None

    ticket = Ticket(
        concert_id=concert.id,
        category="VIP",
        price=150.00,
        quantity=100,
        sold=2,
    )

    session.add(ticket)
    session.commit()
    session.refresh(ticket)

    assert ticket.id is not None

    booking = Booking(
        ticket_id=ticket.id,
        attendee="Alyssa Loh",
        quantity=2,
        status="payment_uploaded",
    )

    session.add(booking)
    session.commit()
    session.refresh(booking)

    assert booking.id is not None

    filename = f"booking_{booking.id}_" "admin_review_test.png"

    UPLOAD_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    stored_path = UPLOAD_DIR / filename
    stored_path.write_bytes(PNG_CONTENT)

    proof = PaymentProof(
        booking_id=booking.id,
        filename=filename,
    )

    session.add(proof)
    session.commit()
    session.refresh(proof)

    return booking, proof, stored_path


def test_admin_payment_page_requires_login(
    client: TestClient,
) -> None:
    response = client.get(
        "/admin/payments",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_non_admin_cannot_access_payment_page(
    client: TestClient,
    session: Session,
) -> None:
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
        "/admin/payments",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/concerts"


def test_admin_can_view_uploaded_payment_proof(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(
        session,
        email="admin@example.com",
        role="admin",
    )

    booking, proof, _stored_path = _create_payment_uploaded_booking(session)

    _login(
        client,
        email="admin@example.com",
    )

    response = client.get("/admin/payments")

    assert response.status_code == 200
    assert "Payment Verification" in response.text
    assert "Admin Review Concert" in response.text
    assert "Alyssa Loh" in response.text
    assert "Payment Uploaded" in response.text
    assert "RM 300.00" in response.text
    assert f"/admin/payment-proofs/{proof.id}/file" in response.text
    assert f"/admin/payment-proofs/{proof.id}/approve" in response.text
    assert f"/admin/payment-proofs/{proof.id}/reject" in response.text
    assert f"Booking #{booking.id}" in response.text


def test_admin_can_open_payment_proof_file(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(
        session,
        email="admin@example.com",
        role="admin",
    )

    _booking, proof, _stored_path = _create_payment_uploaded_booking(session)

    _login(
        client,
        email="admin@example.com",
    )

    response = client.get(f"/admin/payment-proofs/{proof.id}/file")

    assert response.status_code == 200
    assert response.content == PNG_CONTENT
    assert response.headers["content-type"].startswith("image/png")


def test_non_admin_cannot_open_payment_proof_file(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(
        session,
        email="attendee@example.com",
        role="attendee",
    )

    _booking, proof, _stored_path = _create_payment_uploaded_booking(session)

    _login(
        client,
        email="attendee@example.com",
    )

    response = client.get(
        f"/admin/payment-proofs/{proof.id}/file",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/concerts"


def test_admin_approval_confirms_booking(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(
        session,
        email="admin@example.com",
        role="admin",
    )

    booking, proof, stored_path = _create_payment_uploaded_booking(session)

    _login(
        client,
        email="admin@example.com",
    )

    response = client.post(
        f"/admin/payment-proofs/{proof.id}/approve",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/admin/payments?message=")

    session.refresh(booking)

    assert booking.status == "confirmed"
    assert session.get(PaymentProof, proof.id) is not None
    assert stored_path.exists()


def test_approved_booking_displays_confirmed_status(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(
        session,
        email="admin@example.com",
        role="admin",
    )

    booking, proof, _stored_path = _create_payment_uploaded_booking(session)

    _login(
        client,
        email="admin@example.com",
    )

    approve_response = client.post(
        f"/admin/payment-proofs/{proof.id}/approve",
        follow_redirects=False,
    )

    assert approve_response.status_code == 303

    booking_response = client.get(f"/bookings/{booking.id}")

    assert booking_response.status_code == 200
    assert "Confirmed" in booking_response.text
    assert "Payment verified. Your booking has been confirmed." in booking_response.text


def test_admin_rejection_reopens_payment_upload(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(
        session,
        email="admin@example.com",
        role="admin",
    )

    booking, proof, stored_path = _create_payment_uploaded_booking(session)

    proof_id = proof.id

    assert proof_id is not None
    assert stored_path.exists()

    _login(
        client,
        email="admin@example.com",
    )

    response = client.post(
        f"/admin/payment-proofs/{proof_id}/reject",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"].startswith("/admin/payments?message=")

    session.refresh(booking)

    assert booking.status == "pending_payment"
    assert session.get(PaymentProof, proof_id) is None
    assert not stored_path.exists()


def test_rejected_booking_allows_replacement_upload(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(
        session,
        email="admin@example.com",
        role="admin",
    )

    booking, proof, _stored_path = _create_payment_uploaded_booking(session)

    assert proof.id is not None
    assert booking.id is not None

    _login(
        client,
        email="admin@example.com",
    )

    reject_response = client.post(
        f"/admin/payment-proofs/{proof.id}/reject",
        follow_redirects=False,
    )

    assert reject_response.status_code == 303

    logout_response = client.post(
        "/logout",
        follow_redirects=False,
    )

    assert logout_response.status_code == 303

    replacement_response = client.post(
        f"/bookings/{booking.id}/payment-proof",
        files={
            "file": (
                "replacement.png",
                PNG_CONTENT,
                "image/png",
            )
        },
        follow_redirects=False,
    )

    assert replacement_response.status_code == 303

    session.refresh(booking)

    assert booking.status == "payment_uploaded"


def test_non_admin_cannot_approve_payment(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(
        session,
        email="attendee@example.com",
        role="attendee",
    )

    booking, proof, _stored_path = _create_payment_uploaded_booking(session)

    _login(
        client,
        email="attendee@example.com",
    )

    response = client.post(
        f"/admin/payment-proofs/{proof.id}/approve",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/concerts"

    session.refresh(booking)

    assert booking.status == "payment_uploaded"


def test_missing_payment_proof_returns_404(
    client: TestClient,
    session: Session,
) -> None:
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
        "/admin/payment-proofs/999999/approve",
        follow_redirects=False,
    )

    assert response.status_code == 404
