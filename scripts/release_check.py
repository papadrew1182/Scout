"""Scout release check: backend tests, TypeScript, and optional full smoke run.

Usage:
    python scripts/release_check.py           # tests + types only
    python scripts/release_check.py --smoke   # full: migrate, seed, start stack, run Playwright

Requires:
    - PostgreSQL running (scout_test DB for tests, scout DB for smoke)
    - Node.js + npm
    - Backend deps installed (pip install -r backend/requirements.txt)
"""

import argparse
import os
import signal
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
FRONTEND = os.path.join(ROOT, "scout-ui")
SMOKE = os.path.join(ROOT, "smoke-tests")
PYTHON = sys.executable

_children: list[subprocess.Popen] = []


def run(cmd, cwd=ROOT, env=None, check=True):
    print(f"\n{'='*60}\n  {cmd}\n{'='*60}")
    merged = {**os.environ, **(env or {})}
    r = subprocess.run(cmd, shell=True, cwd=cwd, env=merged)
    if check and r.returncode != 0:
        print(f"\nFAILED: {cmd}")
        cleanup()
        sys.exit(r.returncode)
    return r


def bg(cmd, cwd=ROOT, env=None):
    """Start a background process, tracked for cleanup."""
    merged = {**os.environ, **(env or {})}
    p = subprocess.Popen(cmd, shell=True, cwd=cwd, env=merged)
    _children.append(p)
    return p


def cleanup():
    for p in _children:
        try:
            p.terminate()
            p.wait(timeout=5)
        except Exception:
            try:
                p.kill()
            except Exception:
                pass
    _children.clear()


def wait_url(url, timeout=30):
    """Wait for URL to return 200."""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from wait_for_url import wait_for_url
    print(f"Waiting for {url} ...")
    if not wait_for_url(url, timeout):
        print(f"FAIL: {url} not reachable after {timeout}s")
        cleanup()
        sys.exit(1)
    print(f"  OK: {url}")


def run_tests():
    run(f"{PYTHON} -m pytest tests/ -v --tb=short", cwd=BACKEND)


def run_types():
    run("npx tsc --noEmit", cwd=FRONTEND)


def run_smoke():
    print("\n--- SMOKE: Migrate + Seed ---")
    run(f"{PYTHON} migrate.py", cwd=BACKEND)
    run(f"{PYTHON} seed_smoke.py", cwd=BACKEND)

    print("\n--- SMOKE: Start backend ---")
    bg(f"{PYTHON} -m uvicorn app.main:app --host localhost --port 8000", cwd=BACKEND)
    wait_url("http://localhost:8000/health", timeout=15)

    print("\n--- SMOKE: Build + serve web ---")
    run("npm install", cwd=FRONTEND)
    run("npx expo export --platform web --clear", cwd=FRONTEND, env={"EXPO_PUBLIC_API_URL": "http://localhost:8000"})
    bg("npx serve dist -s -l tcp://localhost:8081", cwd=FRONTEND)
    wait_url("http://localhost:8081/", timeout=15)

    print("\n--- SMOKE: Install Playwright ---")
    run("npm install", cwd=SMOKE)
    run("npx playwright install chromium", cwd=SMOKE)

    print("\n--- SMOKE: Run tests ---")
    result = run(
        "npx playwright test",
        cwd=SMOKE,
        env={"SCOUT_WEB_URL": "http://localhost:8081"},
        check=False,
    )

    cleanup()

    if result.returncode != 0:
        print("\nSMOKE TESTS FAILED")
        sys.exit(result.returncode)
    print("\nSMOKE TESTS PASSED")


def main():
    parser = argparse.ArgumentParser(description="Scout release check")
    parser.add_argument("--smoke", action="store_true", help="Run full smoke suite (migrate, seed, start stack, Playwright)")
    args = parser.parse_args()

    try:
        print("Scout Release Check")
        print("=" * 60)

        run_tests()
        run_types()

        if args.smoke:
            run_smoke()

        print("\n" + "=" * 60)
        print("  ALL CHECKS PASSED")
        print("=" * 60)
    except SystemExit:
        raise
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        cleanup()
        sys.exit(1)
    finally:
        cleanup()


if __name__ == "__main__":
    main()
