import time
import os
os.environ["COMPOSIO_API_KEY"] = "sk-fake-api-key"

from unittest.mock import MagicMock
from src.integrations.composio import list_connections_summary, active_toolkit_slugs, is_configured
import src.integrations.composio

mock_client = MagicMock()
mock_response = MagicMock()
mock_item1 = MagicMock()
mock_item1.toolkit.slug = "SLUG1"
mock_item1.toolkit.name = "Name 1"
mock_item1.id = "id1"
mock_item1.status = "ACTIVE"
mock_item1.is_disabled = False

mock_item2 = MagicMock()
mock_item2.toolkit.slug = "SLUG2"
mock_item2.toolkit.name = "Name 2"
mock_item2.id = "id2"
mock_item2.status = "ACTIVE"
mock_item2.is_disabled = False

mock_response.items = [mock_item1, mock_item2]
mock_client.connected_accounts.list.return_value = mock_response

src.integrations.composio._client = MagicMock(return_value=mock_client)

def run_bench():
    # Warmup
    list_connections_summary()
    mock_client.connected_accounts.list.reset_mock()

    start = time.monotonic()
    for _ in range(500):
        list_connections_summary()
    end = time.monotonic()
    print(f"Time for 500 calls (list_connections_summary): {end - start:.4f}s")
    print(f"Mock client was called {mock_client.connected_accounts.list.call_count} times")
    mock_client.connected_accounts.list.reset_mock()

    start = time.monotonic()
    for _ in range(500):
        active_toolkit_slugs()
    end = time.monotonic()
    print(f"Time for 500 calls (active_toolkit_slugs): {end - start:.4f}s")
    print(f"Mock client was called {mock_client.connected_accounts.list.call_count} times")


if __name__ == "__main__":
    run_bench()
