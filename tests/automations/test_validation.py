import pytest
from zoneinfo import ZoneInfoNotFoundError

from src.automations.validation import validate_cron_expression, validate_timezone_iana


def test_validate_cron_expression_valid():
    assert validate_cron_expression("0 12 * * *") == "0 12 * * *"
    assert validate_cron_expression("*/5 * * * *") == "*/5 * * * *"
    assert validate_cron_expression("0 0 1 1 *") == "0 0 1 1 *"
    # With spaces around
    assert validate_cron_expression("  0 12 * * *  ") == "0 12 * * *"


def test_validate_cron_expression_invalid_fields_count():
    with pytest.raises(ValueError, match="cron_expression must have exactly 5 fields"):
        validate_cron_expression("0 12 * *")  # 4 fields

    with pytest.raises(ValueError, match="cron_expression must have exactly 5 fields"):
        validate_cron_expression("0 12 * * * *")  # 6 fields


def test_validate_cron_expression_invalid_values():
    # Because croniter's CroniterBadCronError is a subclass of ValueError,
    # catching ValueError will work.
    with pytest.raises(ValueError):
        validate_cron_expression("60 12 * * *")  # Invalid minute

    with pytest.raises(ValueError):
        validate_cron_expression("0 25 * * *")  # Invalid hour

    with pytest.raises(ValueError):
        validate_cron_expression("0 12 32 * *")  # Invalid day

    with pytest.raises(ValueError):
        validate_cron_expression("0 12 * 13 *")  # Invalid month

    with pytest.raises(ValueError):
        validate_cron_expression("0 12 * * 8")  # Invalid day of week


def test_validate_cron_expression_invalid_characters():
    with pytest.raises(ValueError):
        validate_cron_expression("a b c d e")


def test_validate_timezone_iana_valid():
    assert validate_timezone_iana("UTC") == "UTC"
    assert validate_timezone_iana("America/New_York") == "America/New_York"
    assert validate_timezone_iana("  Europe/London  ") == "Europe/London"


def test_validate_timezone_iana_invalid():
    with pytest.raises(ZoneInfoNotFoundError):
        validate_timezone_iana("Invalid/Timezone")
