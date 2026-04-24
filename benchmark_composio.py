import time
from src.integrations.composio import list_connections_summary

def run_bench():
    start = time.monotonic()
    for _ in range(5):
        list_connections_summary()
    end = time.monotonic()
    print(f"Time for 5 calls: {end - start:.4f}s")

if __name__ == "__main__":
    run_bench()
