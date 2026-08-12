from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException
from sqlmodel import Session, select

from concert_portal.models import Concert, ConcertPoster
from concert_portal.web import UPLOAD_DIR

MAX_POSTER_SIZE = 5 * 1024 * 1024

ALLOWED_POSTER_TYPES = {
    ".jpg": {"image/jpeg", "image/jpg"},
    ".jpeg": {"image/jpeg", "image/jpg"},
    ".png": {"image/png"},
}


def get_concert_for_poster(
    concert_id: int,
    session: Session,
) -> Concert:
    """Return the concert receiving a poster."""

    concert = session.get(
        Concert,
        concert_id,
    )

    if concert is None:
        raise HTTPException(
            status_code=404,
            detail="Concert not found.",
        )

    return concert


def validate_concert_poster(
    *,
    filename: str | None,
    content_type: str | None,
    content: bytes,
) -> str:
    """Validate concert poster extension, MIME type, size and signature."""

    if filename is None or not filename.strip():
        raise HTTPException(
            status_code=422,
            detail="Select a concert poster to upload.",
        )

    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_POSTER_TYPES:
        raise HTTPException(
            status_code=422,
            detail="Concert poster must be a JPG, JPEG or PNG image.",
        )

    allowed_types = ALLOWED_POSTER_TYPES[extension]

    if content_type not in allowed_types:
        raise HTTPException(
            status_code=422,
            detail=("The uploaded poster type does not match " "its filename extension."),
        )

    if not content:
        raise HTTPException(
            status_code=422,
            detail="The uploaded concert poster is empty.",
        )

    if len(content) > MAX_POSTER_SIZE:
        raise HTTPException(
            status_code=413,
            detail="Concert poster files must not exceed 5 MB.",
        )

    if extension in {".jpg", ".jpeg"}:
        valid_signature = content.startswith(b"\xff\xd8\xff")
    else:
        valid_signature = content.startswith(b"\x89PNG\r\n\x1a\n")

    if not valid_signature:
        image_type = extension.removeprefix(".").upper()

        raise HTTPException(
            status_code=422,
            detail=("The uploaded file content is not " f"a valid {image_type} image."),
        )

    return extension


def generate_concert_poster_filename(
    concert_id: int,
    extension: str,
) -> str:
    """Generate a safe server-controlled poster filename."""

    return f"concert_{concert_id}_poster_" f"{uuid4().hex}" f"{extension}"


def get_concert_poster(
    concert_id: int,
    session: Session,
) -> ConcertPoster | None:
    """Return the stored poster record for a concert."""

    return session.exec(
        select(ConcertPoster).where(
            ConcertPoster.concert_id == concert_id,
        )
    ).first()


def get_concert_poster_path(
    poster: ConcertPoster,
) -> Path:
    """Resolve a poster path safely."""

    stored_path = (UPLOAD_DIR / Path(poster.filename).name).resolve()

    upload_root = UPLOAD_DIR.resolve()

    if stored_path.parent != upload_root:
        raise HTTPException(
            status_code=404,
            detail="Concert poster file not found.",
        )

    if not stored_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Concert poster file not found.",
        )

    return stored_path


def save_concert_poster(
    concert_id: int,
    stored_filename: str,
    session: Session,
) -> ConcertPoster:
    """Create or replace the poster record for a concert."""

    get_concert_for_poster(
        concert_id,
        session,
    )

    existing = get_concert_poster(
        concert_id,
        session,
    )

    if existing is None:
        poster = ConcertPoster(
            concert_id=concert_id,
            filename=stored_filename,
        )

        session.add(
            poster,
        )
        session.commit()
        session.refresh(
            poster,
        )

        return poster

    old_filename = existing.filename
    existing.filename = stored_filename

    session.add(
        existing,
    )
    session.commit()
    session.refresh(
        existing,
    )

    old_path = (UPLOAD_DIR / Path(old_filename).name).resolve()

    upload_root = UPLOAD_DIR.resolve()

    if old_path.parent == upload_root and old_path.is_file() and old_filename != stored_filename:
        old_path.unlink()

    return existing
