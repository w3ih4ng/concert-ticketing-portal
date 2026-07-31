"""Validation helpers for concert-related input."""

from dataclasses import dataclass
from datetime import date

CONCERT_TITLE_MIN_LENGTH = 3
CONCERT_TITLE_MAX_LENGTH = 100

CONCERT_VENUE_MIN_LENGTH = 2
CONCERT_VENUE_MAX_LENGTH = 100

CONCERT_ORGANISER_MIN_LENGTH = 2
CONCERT_ORGANISER_MAX_LENGTH = 100


@dataclass(frozen=True)
class ValidatedConcert:
    """Clean concert values that are ready to be stored."""

    title: str
    date: str
    venue: str
    organiser: str


def _validate_required_text(
    *,
    field_name: str,
    value: str,
    minimum_length: int,
    maximum_length: int,
    errors: dict[str, str],
) -> str:
    """Trim and validate one required text field."""

    cleaned_value = value.strip()
    field_label = field_name.replace("_", " ").title()

    if not cleaned_value:
        errors[field_name] = f"{field_label} is required."
        return cleaned_value

    if len(cleaned_value) < minimum_length:
        errors[field_name] = f"{field_label} must be at least {minimum_length} characters."
        return cleaned_value

    if len(cleaned_value) > maximum_length:
        errors[field_name] = f"{field_label} must not exceed {maximum_length} characters."

    return cleaned_value


def validate_concert_input(
    *,
    title: str,
    date_value: str,
    venue: str,
    organiser: str,
) -> tuple[ValidatedConcert, dict[str, str]]:
    """Clean and validate concert creation input."""

    errors: dict[str, str] = {}

    cleaned_title = _validate_required_text(
        field_name="title",
        value=title,
        minimum_length=CONCERT_TITLE_MIN_LENGTH,
        maximum_length=CONCERT_TITLE_MAX_LENGTH,
        errors=errors,
    )

    cleaned_venue = _validate_required_text(
        field_name="venue",
        value=venue,
        minimum_length=CONCERT_VENUE_MIN_LENGTH,
        maximum_length=CONCERT_VENUE_MAX_LENGTH,
        errors=errors,
    )

    cleaned_organiser = _validate_required_text(
        field_name="organiser",
        value=organiser,
        minimum_length=CONCERT_ORGANISER_MIN_LENGTH,
        maximum_length=CONCERT_ORGANISER_MAX_LENGTH,
        errors=errors,
    )

    cleaned_date = date_value.strip()

    if not cleaned_date:
        errors["date"] = "Concert date is required."
    else:
        try:
            parsed_date = date.fromisoformat(cleaned_date)
        except ValueError:
            errors["date"] = "Enter a valid concert date."
        else:
            if parsed_date < date.today():
                errors["date"] = "Concert date cannot be earlier than today."

    validated_concert = ValidatedConcert(
        title=cleaned_title,
        date=cleaned_date,
        venue=cleaned_venue,
        organiser=cleaned_organiser,
    )

    return validated_concert, errors
