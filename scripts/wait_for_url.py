"""Wait for a URL to return HTTP 200. Cross-platform, no dependencies beyond stdlib.

Usage:
    python scripts/wait_for_url.py http://localhost:8000/health --timeout 30
"""

import sys
import time
import urllib.request
import urllib.error


def wait_for_url(url: str, timeout: int = 30, interval: float = 1.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            resp = urllib.request.urlopen(url, timeout=3)
            if resp.status == 200:
                return True
        except (urllib.error.URLError, OSError, TimeoutError):
            pass
        time.sleep(interval)
    return False


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000/health"
    timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    print(f"Waiting for {url} (timeout {timeout}s)...")
    if wait_for_url(url, timeout):
        print(f"  OK: {url} is reachable")
        sys.exit(0)
    else:
        print(f"  FAIL: {url} not reachable after {timeout}s")
        sys.exit(1)
