from pathlib import Path

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from concert_portal.models import Concert, ConcertPoster
from concert_portal.web import UPLOAD_DIR

PNG_CONTENT = b"\x89PNG\r\n\x1a\n" b"test-poster-content"

JPEG_CONTENT = b"\xff\xd8\xff" b"test-jpeg-poster"


def _create_concert(
    session: Session,
) -> Concert:
    """Create a concert for poster tests."""

    concert = Concert(
        title="Poster Test Concert",
        date="2030-08-01",
        venue="Test Stadium",
        organiser="Test Organiser",
    )

    session.add(concert)
    session.commit()
    session.refresh(concert)

    return concert


def _cleanup_poster_file(
    filename: str,
) -> None:
    """Remove a poster file created during a test."""

    path = UPLOAD_DIR / Path(filename).name

    if path.is_file():
        path.unlink()


def test_concert_page_contains_poster_upload_form(
    client: TestClient,
    session: Session,
) -> None:
    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    response = client.get(
        f"/concerts/{concert.id}",
    )

    assert response.status_code == 200
    assert "Concert Poster" in response.text
    assert 'name="poster"' in response.text
    assert f"/concerts/{concert.id}/poster" in response.text


def test_valid_png_poster_can_be_uploaded(
    client: TestClient,
    session: Session,
) -> None:
    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    response = client.post(
        f"/concerts/{concert.id}/poster",
        files={
            "poster": (
                "poster.png",
                PNG_CONTENT,
                "image/png",
            )
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (f"/concerts/{concert.id}" "?poster_updated=true")

    poster = session.exec(
        select(ConcertPoster).where(
            ConcertPoster.concert_id == concert.id,
        )
    ).first()

    assert poster is not None
    assert poster.filename.endswith(".png")
    assert poster.filename.startswith(f"concert_{concert.id}_poster_")

    path = UPLOAD_DIR / Path(poster.filename).name

    assert path.is_file()
    assert path.read_bytes() == PNG_CONTENT

    _cleanup_poster_file(
        poster.filename,
    )


def test_uploaded_poster_is_displayed(
    client: TestClient,
    session: Session,
) -> None:
    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    response = client.post(
        f"/concerts/{concert.id}/poster",
        files={
            "poster": (
                "poster.jpg",
                JPEG_CONTENT,
                "image/jpeg",
            )
        },
        follow_redirects=False,
    )

    assert response.status_code == 303

    poster = session.exec(
        select(ConcertPoster).where(
            ConcertPoster.concert_id == concert.id,
        )
    ).first()

    assert poster is not None

    page = client.get(
        f"/concerts/{concert.id}",
    )

    assert page.status_code == 200
    assert f'src="/concerts/{concert.id}/poster"' in page.text

    image = client.get(
        f"/concerts/{concert.id}/poster",
    )

    assert image.status_code == 200
    assert image.content == JPEG_CONTENT

    _cleanup_poster_file(
        poster.filename,
    )


def test_invalid_extension_is_rejected(
    client: TestClient,
    session: Session,
) -> None:
    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    response = client.post(
        f"/concerts/{concert.id}/poster",
        files={
            "poster": (
                "poster.txt",
                b"not-an-image",
                "text/plain",
            )
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (f"/concerts/{concert.id}" "?poster_error=422")

    poster = session.exec(
        select(ConcertPoster).where(
            ConcertPoster.concert_id == concert.id,
        )
    ).first()

    assert poster is None


def test_mismatched_content_type_is_rejected(
    client: TestClient,
    session: Session,
) -> None:
    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    response = client.post(
        f"/concerts/{concert.id}/poster",
        files={
            "poster": (
                "poster.png",
                PNG_CONTENT,
                "text/plain",
            )
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (f"/concerts/{concert.id}" "?poster_error=422")


def test_invalid_image_signature_is_rejected(
    client: TestClient,
    session: Session,
) -> None:
    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    response = client.post(
        f"/concerts/{concert.id}/poster",
        files={
            "poster": (
                "poster.png",
                b"not-a-real-png",
                "image/png",
            )
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (f"/concerts/{concert.id}" "?poster_error=422")


def test_large_poster_is_rejected(
    client: TestClient,
    session: Session,
) -> None:
    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    oversized_content = b"\x89PNG\r\n\x1a\n" + b"x" * (5 * 1024 * 1024)

    response = client.post(
        f"/concerts/{concert.id}/poster",
        files={
            "poster": (
                "large.png",
                oversized_content,
                "image/png",
            )
        },
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == (f"/concerts/{concert.id}" "?poster_error=413")


def test_new_poster_replaces_existing_poster(
    client: TestClient,
    session: Session,
) -> None:
    concert = _create_concert(
        session,
    )

    assert concert.id is not None

    first_response = client.post(
        f"/concerts/{concert.id}/poster",
        files={
            "poster": (
                "first.png",
                PNG_CONTENT,
                "image/png",
            )
        },
        follow_redirects=False,
    )

    assert first_response.status_code == 303

    first_poster = session.exec(
        select(ConcertPoster).where(
            ConcertPoster.concert_id == concert.id,
        )
    ).first()

    assert first_poster is not None

    first_filename = first_poster.filename

    second_response = client.post(
        f"/concerts/{concert.id}/poster",
        files={
            "poster": (
                "second.jpg",
                JPEG_CONTENT,
                "image/jpeg",
            )
        },
        follow_redirects=False,
    )

    assert second_response.status_code == 303

    session.refresh(
        first_poster,
    )

    assert first_poster.filename != first_filename
    assert first_poster.filename.endswith(".jpg")

    old_path = UPLOAD_DIR / Path(first_filename).name

    assert not old_path.exists()

    new_path = UPLOAD_DIR / Path(first_poster.filename).name

    assert new_path.is_file()

    _cleanup_poster_file(
        first_poster.filename,
    )


def test_missing_concert_cannot_receive_poster(
    client: TestClient,
) -> None:
    response = client.post(
        "/concerts/99999/poster",
        files={
            "poster": (
                "poster.png",
                PNG_CONTENT,
                "image/png",
            )
        },
        follow_redirects=False,
    )

    assert response.status_code == 404
