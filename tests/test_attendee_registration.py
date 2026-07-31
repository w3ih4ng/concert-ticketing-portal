from fastapi.testclient import TestClient
from pwdlib import PasswordHash
from sqlmodel import Session, select

from concert_portal.models import User

password_hash = PasswordHash.recommended()


def _valid_attendee(**overrides: str) -> dict[str, str]:
    payload = {
        "name": "Alyssa Loh",
        "email": "alyssa@example.com",
        "phone": "012-3456789",
        "password": "Password123",
    }

    payload.update(overrides)
    return payload


# ---------- API ----------


def test_attendee_api_registers_user(
    client: TestClient,
    session: Session,
) -> None:
    response = client.post(
        "/users/attendees",
        json=_valid_attendee(
            name="  Alyssa   Loh  ",
            email="  ALYSSA@EXAMPLE.COM  ",
        ),
    )

    assert response.status_code == 201

    data = response.json()

    assert data["name"] == "Alyssa Loh"
    assert data["email"] == "alyssa@example.com"
    assert data["phone"] == "012-3456789"
    assert data["role"] == "attendee"
    assert "password" not in data
    assert "password_hash" not in data

    user = session.exec(select(User).where(User.email == "alyssa@example.com")).first()

    assert user is not None
    assert user.password_hash != "Password123"
    assert password_hash.verify("Password123", user.password_hash)


def test_attendee_api_rejects_duplicate_email(
    client: TestClient,
) -> None:
    first_response = client.post(
        "/users/attendees",
        json=_valid_attendee(),
    )

    assert first_response.status_code == 201

    second_response = client.post(
        "/users/attendees",
        json=_valid_attendee(
            name="Another Person",
            email="ALYSSA@EXAMPLE.COM",
        ),
    )

    assert second_response.status_code == 409
    assert "email" in second_response.json()["detail"]


def test_attendee_api_rejects_blank_name(
    client: TestClient,
) -> None:
    response = client.post(
        "/users/attendees",
        json=_valid_attendee(name="   "),
    )

    assert response.status_code == 422
    assert "name" in response.json()["detail"]


def test_attendee_api_rejects_invalid_email(
    client: TestClient,
) -> None:
    response = client.post(
        "/users/attendees",
        json=_valid_attendee(email="not-an-email"),
    )

    assert response.status_code == 422
    assert "email" in response.json()["detail"]


def test_attendee_api_rejects_invalid_phone(
    client: TestClient,
) -> None:
    response = client.post(
        "/users/attendees",
        json=_valid_attendee(phone="abc123"),
    )

    assert response.status_code == 422
    assert "phone" in response.json()["detail"]


def test_attendee_api_rejects_weak_password(
    client: TestClient,
) -> None:
    response = client.post(
        "/users/attendees",
        json=_valid_attendee(password="password"),
    )

    assert response.status_code == 422
    assert "password" in response.json()["detail"]


# ---------- HTML form ----------


def test_attendee_registration_page_is_available(
    client: TestClient,
) -> None:
    response = client.get("/register/attendee")

    assert response.status_code == 200
    assert "Create Attendee Account" in response.text
    assert 'action="/register/attendee"' in response.text


def test_attendee_form_preserves_safe_values_on_error(
    client: TestClient,
) -> None:
    response = client.post(
        "/register/attendee",
        data=_valid_attendee(password="short"),
    )

    assert response.status_code == 422
    assert 'value="Alyssa Loh"' in response.text
    assert 'value="alyssa@example.com"' in response.text
    assert 'value="012-3456789"' in response.text
    assert "Password must be at least 8 characters." in response.text
    assert 'value="short"' not in response.text


def test_attendee_form_rejects_duplicate_email(
    client: TestClient,
) -> None:
    first_response = client.post(
        "/register/attendee",
        data=_valid_attendee(),
        follow_redirects=False,
    )

    assert first_response.status_code == 303

    second_response = client.post(
        "/register/attendee",
        data=_valid_attendee(email="ALYSSA@EXAMPLE.COM"),
    )

    assert second_response.status_code == 422
    assert "An account with this email already exists." in second_response.text


def test_attendee_form_registers_and_redirects(
    client: TestClient,
    session: Session,
) -> None:
    response = client.post(
        "/register/attendee",
        data=_valid_attendee(),
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == ("/register/attendee?registered=true")

    user = session.exec(select(User).where(User.email == "alyssa@example.com")).first()

    assert user is not None
    assert user.role == "attendee"


def test_attendee_registration_success_message(
    client: TestClient,
) -> None:
    response = client.post(
        "/register/attendee",
        data=_valid_attendee(),
        follow_redirects=False,
    )

    followed = client.get(response.headers["location"])

    assert followed.status_code == 200
    assert "Registration successful" in followed.text


def test_attendee_form_handles_all_blank_fields(
    client: TestClient,
) -> None:
    response = client.post(
        "/register/attendee",
        data={
            "name": "",
            "email": "",
            "phone": "",
            "password": "",
        },
    )

    assert response.status_code == 422
    assert "Name cannot be blank." in response.text
    assert "Email cannot be blank." in response.text
    assert "Phone number cannot be blank." in response.text
    assert "Password cannot be blank." in response.text
