import pytest

from src.automations.validation import validate_timezone_iana


def test_validate_timezone_iana_valid():
    assert validate_timezone_iana("UTC") == "UTC"
    assert validate_timezone_iana("America/New_York") == "America/New_York"
    assert validate_timezone_iana("Europe/London") == "Europe/London"
    assert validate_timezone_iana("  Europe/London  ") == "Europe/London"


def test_validate_timezone_iana_padded():
    assert validate_timezone_iana("  UTC  ") == "UTC"
    assert validate_timezone_iana("  America/Los_Angeles") == "America/Los_Angeles"


def test_validate_timezone_iana_invalid():
    with pytest.raises(ValueError, match="Invalid IANA timezone: Invalid/Timezone"):
        validate_timezone_iana("Invalid/Timezone")

    with pytest.raises(ValueError, match="Invalid IANA timezone: Not/A_Timezone"):
        validate_timezone_iana("Not/A_Timezone")

    with pytest.raises(ValueError, match=r"Invalid IANA timezone: GMT\+1"):
        validate_timezone_iana("GMT+1")  # GMT+1 isn't a valid strict IANA timezone generally
