import pytest
from zoneinfo import ZoneInfoNotFoundError
from src.automations.validation import validate_timezone_iana

def test_validate_timezone_iana_valid():
    assert validate_timezone_iana("UTC") == "UTC"
    assert validate_timezone_iana("America/New_York") == "America/New_York"
    assert validate_timezone_iana("  Europe/London  ") == "Europe/London"

def test_validate_timezone_iana_invalid():
    with pytest.raises(ZoneInfoNotFoundError):
        validate_timezone_iana("Invalid/Timezone")
