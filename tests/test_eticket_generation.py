from sqlmodel import Session, select

from concert_portal.models import (
    Booking,
    Concert,
    ETicket,
    PaymentProof,
    Ticket,
)
from concert_portal.services.etickets import (
    generate_eticket,
    get_eticket_for_booking,
)
from concert_portal.services.payments import (
    approve_payment_proof,
)


def _create_payment_uploaded_booking(
    session: Session,
) -> tuple[Booking, PaymentProof]:
    """Create a booking ready for administrator payment approval."""

    concert = Concert(
        title="E-Ticket Concert",
        date="2030-08-20",
        venue="National Arena",
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

    ticket = Ticket(
        concert_id=concert.id,
        category="Standard",
        price=100.00,
        quantity=100,
    )

    session.add(
        ticket,
    )
    session.commit()
    session.refresh(
        ticket,
    )

    assert ticket.id is not None

    booking = Booking(
        ticket_id=ticket.id,
        attendee="E-Ticket Attendee",
        quantity=1,
        status="payment_uploaded",
    )

    session.add(
        booking,
    )
    session.commit()
    session.refresh(
        booking,
    )

    assert booking.id is not None

    proof = PaymentProof(
        booking_id=booking.id,
        filename="payment-proof.png",
    )

    session.add(
        proof,
    )
    session.commit()
    session.refresh(
        proof,
    )

    assert proof.id is not None

    return booking, proof


def test_payment_approval_generates_eticket(
    session: Session,
) -> None:
    """Approving payment creates an e-ticket for the booking."""

    booking, proof = _create_payment_uploaded_booking(
        session,
    )

    assert booking.id is not None
    assert proof.id is not None

    approve_payment_proof(
        proof.id,
        session,
    )

    eticket = get_eticket_for_booking(
        booking.id,
        session,
    )

    assert eticket is not None
    assert eticket.booking_id == booking.id
    assert eticket.ticket_code.startswith(
        "ET-",
    )
    assert eticket.generated_at is not None


def test_payment_approval_confirms_booking(
    session: Session,
) -> None:
    """The booking remains confirmed when its e-ticket is generated."""

    booking, proof = _create_payment_uploaded_booking(
        session,
    )

    assert booking.id is not None
    assert proof.id is not None

    approve_payment_proof(
        proof.id,
        session,
    )

    session.refresh(
        booking,
    )

    assert booking.status == "confirmed"


def test_unapproved_booking_has_no_eticket(
    session: Session,
) -> None:
    """An uploaded payment proof alone must not generate an e-ticket."""

    booking, _ = _create_payment_uploaded_booking(
        session,
    )

    assert booking.id is not None

    eticket = get_eticket_for_booking(
        booking.id,
        session,
    )

    assert eticket is None


def test_generate_eticket_does_not_duplicate(
    session: Session,
) -> None:
    """Generating twice for the same booking returns one e-ticket."""

    booking, _ = _create_payment_uploaded_booking(
        session,
    )

    assert booking.id is not None

    first = generate_eticket(
        booking,
        session,
    )

    session.commit()
    session.refresh(
        first,
    )

    second = generate_eticket(
        booking,
        session,
    )

    session.commit()

    etickets = session.exec(
        select(ETicket).where(
            ETicket.booking_id == booking.id,
        )
    ).all()

    assert first.id == second.id
    assert len(etickets) == 1


def test_different_bookings_receive_different_codes(
    session: Session,
) -> None:
    """Each generated e-ticket receives a different ticket code."""

    first_booking, first_proof = _create_payment_uploaded_booking(
        session,
    )

    second_booking, second_proof = _create_payment_uploaded_booking(
        session,
    )

    assert first_booking.id is not None
    assert second_booking.id is not None
    assert first_proof.id is not None
    assert second_proof.id is not None

    approve_payment_proof(
        first_proof.id,
        session,
    )

    approve_payment_proof(
        second_proof.id,
        session,
    )

    first_eticket = get_eticket_for_booking(
        first_booking.id,
        session,
    )

    second_eticket = get_eticket_for_booking(
        second_booking.id,
        session,
    )

    assert first_eticket is not None
    assert second_eticket is not None

    assert first_eticket.ticket_code != second_eticket.ticket_code
