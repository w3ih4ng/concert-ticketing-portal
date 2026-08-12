from fastapi.testclient import TestClient
from sqlmodel import Session

from concert_portal.models import User
from concert_portal.security import password_hash


def _create_user(
    session: Session,
    *,
    name: str = "Alyssa Test",
    email: str = "alyssa@example.com",
    phone: str = "0123456789",
    password: str = "Password123",
    role: str = "attendee",
) -> User:
    user = User(
        name=name,
        email=email,
        phone=phone,
        role=role,
        password_hash=password_hash.hash(password),
    )

    session.add(user)
    session.commit()
    session.refresh(user)

    return user


def _login(
    client: TestClient,
    *,
    email: str = "alyssa@example.com",
    password: str = "Password123",
) -> None:
    response = client.post(
        "/login",
        data={
            "email": email,
            "password": password,
        },
        follow_redirects=False,
    )

    assert response.status_code == 303


def test_profile_requires_login(
    client: TestClient,
) -> None:
    response = client.get(
        "/profile",
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_profile_displays_current_user_details(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(session)

    _login(client)

    response = client.get(
        "/profile",
    )

    assert response.status_code == 200
    assert "My Profile" in response.text
    assert "Alyssa Test" in response.text
    assert "alyssa@example.com" in response.text
    assert "0123456789" in response.text


def test_user_can_update_profile(
    client: TestClient,
    session: Session,
) -> None:
    user = _create_user(session)

    assert user.id is not None

    _login(client)

    response = client.post(
        "/profile",
        data={
            "name": "Alyssa Updated",
            "email": "updated@example.com",
            "phone": "0198765432",
            "password": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/profile?updated=true"

    session.refresh(user)

    assert user.name == "Alyssa Updated"
    assert user.email == "updated@example.com"
    assert user.phone == "0198765432"


def test_user_can_keep_existing_email(
    client: TestClient,
    session: Session,
) -> None:
    user = _create_user(session)

    _login(client)

    response = client.post(
        "/profile",
        data={
            "name": "Alyssa Updated",
            "email": "alyssa@example.com",
            "phone": "0123456789",
            "password": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    session.refresh(user)

    assert user.email == "alyssa@example.com"


def test_duplicate_email_is_rejected(
    client: TestClient,
    session: Session,
) -> None:
    user = _create_user(session)

    _create_user(
        session,
        name="Other User",
        email="other@example.com",
        phone="0111111111",
    )

    _login(client)

    response = client.post(
        "/profile",
        data={
            "name": "Alyssa Test",
            "email": "other@example.com",
            "phone": "0123456789",
            "password": "",
        },
    )

    assert response.status_code == 409
    assert "An account with this email already exists." in response.text

    session.refresh(user)

    assert user.email == "alyssa@example.com"


def test_invalid_profile_values_are_rejected(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(session)

    _login(client)

    response = client.post(
        "/profile",
        data={
            "name": "",
            "email": "not-an-email",
            "phone": "abc",
            "password": "",
        },
    )

    assert response.status_code == 422
    assert "Name cannot be blank." in response.text
    assert "Enter a valid email address." in response.text
    assert "Phone number contains invalid characters." in response.text


def test_password_is_unchanged_when_blank(
    client: TestClient,
    session: Session,
) -> None:
    user = _create_user(session)

    original_hash = user.password_hash

    _login(client)

    response = client.post(
        "/profile",
        data={
            "name": "Alyssa Test",
            "email": "alyssa@example.com",
            "phone": "0123456789",
            "password": "",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    session.refresh(user)

    assert user.password_hash == original_hash
    assert password_hash.verify(
        "Password123",
        user.password_hash,
    )


def test_user_can_change_password(
    client: TestClient,
    session: Session,
) -> None:
    user = _create_user(session)

    _login(client)

    response = client.post(
        "/profile",
        data={
            "name": "Alyssa Test",
            "email": "alyssa@example.com",
            "phone": "0123456789",
            "password": "NewPassword456",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    session.refresh(user)

    assert password_hash.verify(
        "NewPassword456",
        user.password_hash,
    )
    assert not password_hash.verify(
        "Password123",
        user.password_hash,
    )


def test_short_new_password_is_rejected(
    client: TestClient,
    session: Session,
) -> None:
    _create_user(session)

    _login(client)

    response = client.post(
        "/profile",
        data={
            "name": "Alyssa Test",
            "email": "alyssa@example.com",
            "phone": "0123456789",
            "password": "abc1",
        },
    )

    assert response.status_code == 422
    assert "Password must be at least 8 characters." in response.text


def test_logged_in_user_cannot_update_another_account(
    client: TestClient,
    session: Session,
) -> None:
    current_user = _create_user(session)

    other_user = _create_user(
        session,
        name="Other User",
        email="other@example.com",
        phone="0111111111",
    )

    assert other_user.id is not None

    _login(client)

    response = client.post(
        "/profile",
        data={
            "name": "Changed Name",
            "email": "alyssa@example.com",
            "phone": "0123456789",
            "password": "",
            "user_id": str(other_user.id),
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    session.refresh(current_user)
    session.refresh(other_user)

    assert current_user.name == "Changed Name"
    assert other_user.name == "Other User"
