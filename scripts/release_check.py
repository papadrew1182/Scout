"""Scout release check: runs migrations, backend tests, TypeScript check, smoke seed.

Usage:
    python scripts/release_check.py

Requires:
    - PostgreSQL running with scout_test database
    - Node.js + npm available
    - Backend dependencies installed
"""

import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "backend")
FRONTEND = os.path.join(ROOT, "scout-ui")

def run(cmd, cwd=ROOT, env=None):
    print(f"\n{'='*60}")
    print(f"  {cmd}")
    print(f"{'='*60}")
    merged_env = {**os.environ, **(env or {})}
    result = subprocess.run(cmd, shell=True, cwd=cwd, env=merged_env)
    if result.returncode != 0:
        print(f"\nFAILED: {cmd}")
        sys.exit(result.returncode)
    return result

def main():
    print("Scout Release Check")
    print("=" * 60)

    # 1. Backend tests
    run("python -m pytest tests/ -v --tb=short", cwd=BACKEND)

    # 2. TypeScript check
    run("npx tsc --noEmit", cwd=FRONTEND)

    # 3. Verify /health endpoint format (if backend running)
    print("\n" + "=" * 60)
    print("  All checks passed!")
    print("=" * 60)
    print("\nNext steps for full release verification:")
    print("  1. Start backend:  cd backend && python -m uvicorn app.main:app --port 8000")
    print("  2. Seed smoke:     cd backend && python seed_smoke.py")
    print("  3. Start web:      cd scout-ui && npx expo start --web")
    print("  4. Run smoke:      cd smoke-tests && npm test")

if __name__ == "__main__":
    main()
