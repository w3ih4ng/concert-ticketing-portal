from fastapi.testclient import TestClient
from pwdlib import PasswordHash
from sqlmodel import Session, select

from concert_portal.models import OrganiserProfile, User

password_hash = PasswordHash.recommended()


def _valid_organiser(**overrides: str) -> dict[str, str]:
    payload = {
        "name": "Event Organiser",
        "email": "organiser@example.com",
        "phone": "012-3456789",
        "password": "Password123",
        "organisation_name": "Live Events Malaysia",
        "registration_number": "202601234567",
        "organisation_address": "10 Jalan Concert, Kuala Lumpur",
    }

    payload.update(overrides)
    return payload


def test_organiser_api_registers_pending_request(
    client: TestClient,
    session: Session,
) -> None:
    response = client.post(
        "/users/organisers",
        json=_valid_organiser(
            name="  Event   Organiser  ",
            email="  ORGANISER@EXAMPLE.COM ",
            organisation_name="  Live   Events Malaysia ",
            registration_number=" abc-123 ",
        ),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "Event Organiser"
    assert data["email"] == "organiser@example.com"
    assert data["role"] == "organiser"
    assert data["organisation_name"] == "Live Events Malaysia"
    assert data["registration_number"] == "ABC-123"
    assert data["status"] == "pending"
    assert "password" not in data
    assert "password_hash" not in data

    user = session.exec(select(User).where(User.email == "organiser@example.com")).first()

    assert user is not None
    assert user.role == "organiser"
    assert user.password_hash != "Password123"
    assert password_hash.verify("Password123", user.password_hash)

    profile = session.exec(
        select(OrganiserProfile).where(OrganiserProfile.user_id == user.id)
    ).first()

    assert profile is not None
    assert profile.status == "pending"


def test_organiser_api_rejects_duplicate_email(
    client: TestClient,
) -> None:
    first_response = client.post(
        "/users/organisers",
        json=_valid_organiser(),
    )

    assert first_response.status_code == 201

    second_response = client.post(
        "/users/organisers",
        json=_valid_organiser(
            registration_number="DIFFERENT-123",
            email="ORGANISER@EXAMPLE.COM",
        ),
    )

    assert second_response.status_code == 409
    assert "email" in second_response.json()["detail"]


def test_organiser_api_rejects_duplicate_registration_number(
    client: TestClient,
) -> None:
    first_response = client.post(
        "/users/organisers",
        json=_valid_organiser(),
    )

    assert first_response.status_code == 201

    second_response = client.post(
        "/users/organisers",
        json=_valid_organiser(
            email="second@example.com",
            registration_number="202601234567",
        ),
    )

    assert second_response.status_code == 409
    assert "registration_number" in second_response.json()["detail"]


def test_organiser_api_rejects_blank_organisation_name(
    client: TestClient,
) -> None:
    response = client.post(
        "/users/organisers",
        json=_valid_organiser(organisation_name="   "),
    )

    assert response.status_code == 422
    assert "organisation_name" in response.json()["detail"]


def test_organiser_api_rejects_invalid_registration_number(
    client: TestClient,
) -> None:
    response = client.post(
        "/users/organisers",
        json=_valid_organiser(registration_number="ABC@123"),
    )

    assert response.status_code == 422
    assert "registration_number" in response.json()["detail"]


def test_organiser_api_rejects_blank_address(
    client: TestClient,
) -> None:
    response = client.post(
        "/users/organisers",
        json=_valid_organiser(organisation_address=""),
    )

    assert response.status_code == 422
    assert "organisation_address" in response.json()["detail"]


def test_organiser_registration_page_is_available(
    client: TestClient,
) -> None:
    response = client.get("/register/organiser")

    assert response.status_code == 200
    assert "Create Organiser Account" in response.text
    assert 'action="/register/organiser"' in response.text


def test_organiser_form_handles_all_blank_fields(
    client: TestClient,
) -> None:
    response = client.post(
        "/register/organiser",
        data={
            "name": "",
            "email": "",
            "phone": "",
            "password": "",
            "organisation_name": "",
            "registration_number": "",
            "organisation_address": "",
        },
    )

    assert response.status_code == 422
    assert "Name cannot be blank." in response.text
    assert "Email cannot be blank." in response.text
    assert "Phone number cannot be blank." in response.text
    assert "Password cannot be blank." in response.text
    assert "Organisation name cannot be blank." in response.text
    assert "Organisation registration number cannot be blank." in response.text
    assert "Organisation address cannot be blank." in response.text


def test_organiser_form_preserves_safe_values_on_error(
    client: TestClient,
) -> None:
    response = client.post(
        "/register/organiser",
        data=_valid_organiser(password="short"),
    )

    assert response.status_code == 422
    assert 'value="Event Organiser"' in response.text
    assert 'value="organiser@example.com"' in response.text
    assert 'value="Live Events Malaysia"' in response.text
    assert "10 Jalan Concert, Kuala Lumpur" in response.text
    assert 'value="short"' not in response.text


def test_organiser_form_registers_and_redirects(
    client: TestClient,
    session: Session,
) -> None:
    response = client.post(
        "/register/organiser",
        data=_valid_organiser(),
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == ("/register/organiser?registered=true")

    user = session.exec(select(User).where(User.email == "organiser@example.com")).first()

    assert user is not None
    assert user.role == "organiser"

    profile = session.exec(
        select(OrganiserProfile).where(OrganiserProfile.user_id == user.id)
    ).first()

    assert profile is not None
    assert profile.status == "pending"


def test_organiser_registration_success_message(
    client: TestClient,
) -> None:
    response = client.post(
        "/register/organiser",
        data=_valid_organiser(),
        follow_redirects=False,
    )

    followed = client.get(response.headers["location"])

    assert followed.status_code == 200
    assert "Registration submitted successfully" in followed.text
    assert "pending review" in followed.text
