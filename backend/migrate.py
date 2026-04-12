"""Run all SQL migrations in order using psycopg2."""
import os
import glob
import psycopg2

def run_migrations():
    db_url = os.environ.get("SCOUT_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError("No database URL found in SCOUT_DATABASE_URL or DATABASE_URL")

    migrations_dir = os.path.join(os.path.dirname(__file__), "..", "database", "migrations")
    migration_files = sorted(glob.glob(os.path.join(migrations_dir, "*.sql")))

    conn = psycopg2.connect(db_url)
    conn.autocommit = False

    # Create a tracking table if it doesn't exist
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS _scout_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)
    conn.commit()

    for filepath in migration_files:
        filename = os.path.basename(filepath)
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM _scout_migrations WHERE filename = %s", (filename,))
            if cur.fetchone():
                print(f"Skipping {filename} (already applied)")
                continue

        print(f"Applying {filename}...")
        with open(filepath, "r", encoding="utf-8") as f:
            sql = f.read()

        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute("INSERT INTO _scout_migrations (filename) VALUES (%s)", (filename,))
            conn.commit()
            print(f"  Applied {filename}")
        except Exception as e:
            conn.rollback()
            print(f"  ERROR applying {filename}: {e}")
            raise

    conn.close()
    print("All migrations complete.")

if __name__ == "__main__":
    run_migrations()
