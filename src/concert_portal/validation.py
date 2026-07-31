import re
from datetime import date as date_cls
from decimal import Decimal, InvalidOperation

EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)
PHONE_PATTERN = re.compile(r"^[0-9+()\-\s]+$")
REGISTRATION_NUMBER_PATTERN = re.compile(r"^[A-Za-z0-9./()\- ]+$")

USER_NAME_MIN_LEN = 2
USER_NAME_MAX_LEN = 100
PASSWORD_MIN_LEN = 8
PASSWORD_MAX_LEN = 128

ORGANISATION_NAME_MIN_LEN = 2
ORGANISATION_NAME_MAX_LEN = 150
REGISTRATION_NUMBER_MIN_LEN = 2
REGISTRATION_NUMBER_MAX_LEN = 50
ORGANISATION_ADDRESS_MIN_LEN = 5
ORGANISATION_ADDRESS_MAX_LEN = 250

CONCERT_TEXT_FIELDS = ("title", "venue", "organiser")
CONCERT_TEXT_MIN_LEN = 2
CONCERT_TEXT_MAX_LEN = 200

TICKET_CATEGORY_MIN_LEN = 2
TICKET_CATEGORY_MAX_LEN = 100
ATTENDEE_NAME_MIN_LEN = 2
ATTENDEE_NAME_MAX_LEN = 100


def normalize_email(email: str) -> str:
    """Trim and normalize an email address for storage and comparison."""

    return email.strip().lower()


def validate_attendee_registration(
    name: str,
    email: str,
    phone: str,
    password: str,
) -> tuple[dict[str, str], dict[str, str]]:
    """Validate and clean attendee registration values."""

    errors: dict[str, str] = {}

    cleaned_name = " ".join(name.split())
    cleaned_email = normalize_email(email)
    cleaned_phone = phone.strip()

    if not cleaned_name:
        errors["name"] = "Name cannot be blank."
    elif len(cleaned_name) < USER_NAME_MIN_LEN:
        errors["name"] = f"Name must be at least {USER_NAME_MIN_LEN} characters."
    elif len(cleaned_name) > USER_NAME_MAX_LEN:
        errors["name"] = f"Name must be under {USER_NAME_MAX_LEN} characters."

    if not cleaned_email:
        errors["email"] = "Email cannot be blank."
    elif not EMAIL_PATTERN.fullmatch(cleaned_email):
        errors["email"] = "Enter a valid email address."

    digit_count = sum(character.isdigit() for character in cleaned_phone)

    if not cleaned_phone:
        errors["phone"] = "Phone number cannot be blank."
    elif not PHONE_PATTERN.fullmatch(cleaned_phone):
        errors["phone"] = "Phone number contains invalid characters."
    elif digit_count < 7 or digit_count > 15:
        errors["phone"] = "Phone number must contain between 7 and 15 digits."

    if not password:
        errors["password"] = "Password cannot be blank."
    elif len(password) < PASSWORD_MIN_LEN:
        errors["password"] = f"Password must be at least {PASSWORD_MIN_LEN} characters."
    elif len(password) > PASSWORD_MAX_LEN:
        errors["password"] = f"Password must not exceed {PASSWORD_MAX_LEN} characters."
    elif not any(character.isalpha() for character in password):
        errors["password"] = "Password must contain at least one letter."
    elif not any(character.isdigit() for character in password):
        errors["password"] = "Password must contain at least one number."

    values = {
        "name": cleaned_name,
        "email": cleaned_email,
        "phone": cleaned_phone,
    }

    return errors, values


def validate_organiser_registration(
    name: str,
    email: str,
    phone: str,
    password: str,
    organisation_name: str,
    registration_number: str,
    organisation_address: str,
) -> tuple[dict[str, str], dict[str, str]]:
    """Validate personal and organisation registration information."""

    errors, values = validate_attendee_registration(
        name,
        email,
        phone,
        password,
    )

    cleaned_organisation_name = " ".join(organisation_name.split())
    cleaned_registration_number = registration_number.strip().upper()
    cleaned_organisation_address = " ".join(organisation_address.split())

    if not cleaned_organisation_name:
        errors["organisation_name"] = "Organisation name cannot be blank."
    elif len(cleaned_organisation_name) < ORGANISATION_NAME_MIN_LEN:
        errors["organisation_name"] = (
            "Organisation name must be at least " f"{ORGANISATION_NAME_MIN_LEN} characters."
        )
    elif len(cleaned_organisation_name) > ORGANISATION_NAME_MAX_LEN:
        errors["organisation_name"] = (
            "Organisation name must be under " f"{ORGANISATION_NAME_MAX_LEN} characters."
        )

    if not cleaned_registration_number:
        errors["registration_number"] = "Organisation registration number cannot be blank."
    elif len(cleaned_registration_number) < REGISTRATION_NUMBER_MIN_LEN:
        errors["registration_number"] = (
            "Organisation registration number must be at least "
            f"{REGISTRATION_NUMBER_MIN_LEN} characters."
        )
    elif len(cleaned_registration_number) > REGISTRATION_NUMBER_MAX_LEN:
        errors["registration_number"] = (
            "Organisation registration number must be under "
            f"{REGISTRATION_NUMBER_MAX_LEN} characters."
        )
    elif not REGISTRATION_NUMBER_PATTERN.fullmatch(cleaned_registration_number):
        errors["registration_number"] = (
            "Organisation registration number contains invalid characters."
        )

    if not cleaned_organisation_address:
        errors["organisation_address"] = "Organisation address cannot be blank."
    elif len(cleaned_organisation_address) < ORGANISATION_ADDRESS_MIN_LEN:
        errors["organisation_address"] = (
            "Organisation address must be at least " f"{ORGANISATION_ADDRESS_MIN_LEN} characters."
        )
    elif len(cleaned_organisation_address) > ORGANISATION_ADDRESS_MAX_LEN:
        errors["organisation_address"] = (
            "Organisation address must be under " f"{ORGANISATION_ADDRESS_MAX_LEN} characters."
        )

    values.update(
        {
            "organisation_name": cleaned_organisation_name,
            "registration_number": cleaned_registration_number,
            "organisation_address": cleaned_organisation_address,
        }
    )

    return errors, values


def validate_concert_fields(title: str, date: str, venue: str, organiser: str) -> dict[str, str]:
    """
    Validate organiser-submitted concert fields.

    Returns a dict of field name -> error message. An empty dict means the
    input is valid. Used by both the JSON API and the HTML form so the two
    paths can never enforce different rules.
    """
    errors: dict[str, str] = {}
    values = {"title": title, "venue": venue, "organiser": organiser}

    for field_name in CONCERT_TEXT_FIELDS:
        trimmed = values[field_name].strip()
        if not trimmed:
            errors[field_name] = f"{field_name.capitalize()} cannot be blank."
        elif len(trimmed) < CONCERT_TEXT_MIN_LEN:
            errors[field_name] = (
                f"{field_name.capitalize()} must be at least {CONCERT_TEXT_MIN_LEN} characters."
            )
        elif len(trimmed) > CONCERT_TEXT_MAX_LEN:
            errors[field_name] = (
                f"{field_name.capitalize()} must be under {CONCERT_TEXT_MAX_LEN} characters."
            )

    try:
        parsed_date = date_cls.fromisoformat(date.strip())
    except ValueError:
        errors["date"] = "Enter a valid date (YYYY-MM-DD)."
    else:
        if parsed_date < date_cls.today():
            errors["date"] = "Date cannot be in the past."

    return errors


def _parse_price(value: str | int | float) -> tuple[float | None, str | None]:
    """Parse and validate a ticket price."""

    raw_value = str(value).strip()

    try:
        parsed_price = Decimal(raw_value)
    except InvalidOperation:
        return None, "Enter a valid ticket price."

    if not parsed_price.is_finite():
        return None, "Enter a valid ticket price."

    if parsed_price < 0:
        return None, "Ticket price cannot be negative."

    return float(parsed_price), None


def _parse_whole_quantity(
    value: str | int | float,
    *,
    field_label: str,
) -> tuple[int | None, str | None]:
    """Parse a strictly positive whole-number quantity."""

    raw_value = str(value).strip()

    if not raw_value:
        return None, f"{field_label} is required."

    try:
        parsed_quantity = Decimal(raw_value)
    except InvalidOperation:
        return None, f"{field_label} must be a whole number."

    if not parsed_quantity.is_finite():
        return None, f"{field_label} must be a whole number."

    if parsed_quantity != parsed_quantity.to_integral_value():
        return None, f"{field_label} must be a whole number."

    quantity = int(parsed_quantity)

    if quantity <= 0:
        return None, f"{field_label} must be at least 1."

    return quantity, None


def validate_ticket_fields(
    category: str,
    price: str | int | float,
    quantity: str | int | float,
) -> tuple[dict[str, str], str, float | None, int | None]:
    """Validate and clean ticket-category fields."""

    errors: dict[str, str] = {}
    cleaned_category = category.strip()

    if not cleaned_category:
        errors["category"] = "Ticket category cannot be blank."
    elif len(cleaned_category) < TICKET_CATEGORY_MIN_LEN:
        errors["category"] = (
            f"Ticket category must be at least {TICKET_CATEGORY_MIN_LEN} characters."
        )
    elif len(cleaned_category) > TICKET_CATEGORY_MAX_LEN:
        errors["category"] = f"Ticket category must be under {TICKET_CATEGORY_MAX_LEN} characters."

    parsed_price, price_error = _parse_price(price)
    if price_error is not None:
        errors["price"] = price_error

    parsed_quantity, quantity_error = _parse_whole_quantity(
        quantity,
        field_label="Ticket quantity",
    )
    if quantity_error is not None:
        errors["quantity"] = quantity_error

    return errors, cleaned_category, parsed_price, parsed_quantity


def validate_booking_fields(
    attendee: str,
    quantity: str | int | float,
    remaining: int,
) -> tuple[dict[str, str], str, int | None]:
    """Validate attendee name, booking quantity, and ticket availability."""

    errors: dict[str, str] = {}
    cleaned_attendee = attendee.strip()

    if not cleaned_attendee:
        errors["attendee"] = "Attendee name cannot be blank."
    elif len(cleaned_attendee) < ATTENDEE_NAME_MIN_LEN:
        errors["attendee"] = f"Attendee name must be at least {ATTENDEE_NAME_MIN_LEN} characters."
    elif len(cleaned_attendee) > ATTENDEE_NAME_MAX_LEN:
        errors["attendee"] = f"Attendee name must be under {ATTENDEE_NAME_MAX_LEN} characters."

    parsed_quantity, quantity_error = _parse_whole_quantity(
        quantity,
        field_label="Booking quantity",
    )

    if quantity_error is not None:
        errors["quantity"] = quantity_error
    elif parsed_quantity is not None and parsed_quantity > remaining:
        errors["quantity"] = f"Only {remaining} ticket(s) remaining."

    return errors, cleaned_attendee, parsed_quantity
