"""Script to safely run Alembic migrations in an ECS deployment task."""

import subprocess
import sys


def run_migrations() -> None:
    """Execute alembic upgrade head and exit with code."""
    print("=== CareerAI Production Database Migration Runner ===")
    print("Executing: alembic upgrade head ...")

    result = subprocess.run(["alembic", "upgrade", "head"], capture_output=True, text=True)

    print("STDOUT:")
    print(result.stdout)

    if result.returncode != 0:
        print("STDERR:")
        print(result.stderr, file=sys.stderr)
        print("ERROR: Database migration failed! Aborting deployment.", file=sys.stderr)
        sys.exit(result.returncode)

    print("SUCCESS: Database schema is up to date with head revision.")


if __name__ == "__main__":
    run_migrations()
