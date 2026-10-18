"""Create/upgrade the TRACEVERIFY schema and sync the correlation rule registry.

Usage (from backend/):
    python -m scripts.init_db            # apply schema + pending migrations
    python -m scripts.init_db --reset    # DROP all TRACEVERIFY tables first (destroys data)
"""
import argparse

from app.database.migrate import apply_migrations, drop_all
from app.database.session import engine
from app.repositories.rule_repository import sync_rules


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--reset", action="store_true", help="drop all TRACEVERIFY tables first")
    args = parser.parse_args()
    if args.reset:
        drop_all(engine)
        print("Dropped existing TRACEVERIFY tables.")
    applied = apply_migrations(engine)
    print(f"Schema up to date (baseline + {len(applied)} new migration(s)).")
    print(f"Correlation rules synced: {sync_rules(engine)}")


if __name__ == "__main__":
    main()
