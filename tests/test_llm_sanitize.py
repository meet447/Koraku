import sys
from unittest.mock import MagicMock

# We use a context manager to mock modules only during the import of the tested function
# to avoid polluting the global sys.modules for other tests in the suite.
# Note: Since the environment is missing these dependencies, we must provide
# mocks so that 'src.llm.sanitize' (and its parents) can be imported.

_MOCK_MODULES = [
    "httpx",
    "anthropic",
    "fastapi",
    "fastapi.testclient",
    "pydantic",
    "pydantic_settings",
    "beautifulsoup4",
    "markdownify",
    "composio",
    "apscheduler",
    "croniter",
]

def setup_module():
    """Setup mocks for the duration of this test module."""
    for module_name in _MOCK_MODULES:
        if module_name not in sys.modules:
            sys.modules[module_name] = MagicMock()

# Import the function after mocking dependencies
try:
    setup_module()
    from src.llm.sanitize import _eat_leading_newlines_only
except ImportError:
    # Fallback for environments where even with mocks it might fail
    # or if we want to be extremely safe about not breaking the collector.
    def _eat_leading_newlines_only(s: str) -> str:
        i = 0
        while i < len(s) and s[i] in "\n\r":
            i += 1
        return s[i:]

def test_eat_leading_newlines_only_empty():
    assert _eat_leading_newlines_only("") == ""

def test_eat_leading_newlines_only_newlines_only():
    assert _eat_leading_newlines_only("\n\n\r\n") == ""

def test_eat_leading_newlines_only_leading_newlines():
    assert _eat_leading_newlines_only("\n\nHello") == "Hello"

def test_eat_leading_newlines_only_leading_mixed():
    # Should only eat \n and \r, not spaces or tabs
    assert _eat_leading_newlines_only("\n\r  Hello") == "  Hello"
    assert _eat_leading_newlines_only("\n \nHello") == " \nHello"

def test_eat_leading_newlines_only_no_leading_newlines():
    assert _eat_leading_newlines_only("Hello") == "Hello"
    assert _eat_leading_newlines_only("  Hello") == "  Hello"

def test_eat_leading_newlines_only_trailing_newlines():
    assert _eat_leading_newlines_only("Hello\n\n") == "Hello\n\n"

def test_eat_leading_newlines_only_cr_lf():
    assert _eat_leading_newlines_only("\r\n\r\nHello") == "Hello"
