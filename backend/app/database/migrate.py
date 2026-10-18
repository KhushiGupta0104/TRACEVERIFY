"""Minimal migration runner.

database/schema.sql is the baseline (version 1). Later changes go in
database/migrations/NNN_description.sql and are applied once, in order.
"""
import re
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.config import PROJECT_ROOT

SCHEMA_FILE = PROJECT_ROOT / "database" / "schema.sql"
MIGRATIONS_DIR = PROJECT_ROOT / "database" / "migrations"


def _execute_sql_file(engine: Engine, path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.exec_driver_sql(sql)


def apply_migrations(engine: Engine) -> list[str]:
    """Apply the baseline schema and any pending numbered migrations. Returns applied file names."""
    _execute_sql_file(engine, SCHEMA_FILE)
    applied: list[str] = []
    with engine.connect() as conn:
        done = {row[0] for row in conn.execute(text("SELECT version FROM schema_migrations"))}
    if MIGRATIONS_DIR.exists():
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            match = re.match(r"(\d+)_", path.name)
            if not match or int(match.group(1)) in done:
                continue
            _execute_sql_file(engine, path)
            with engine.begin() as conn:
                conn.execute(text("INSERT INTO schema_migrations (version, name) VALUES (:v, :n)"),
                             {"v": int(match.group(1)), "n": path.stem})
            applied.append(path.name)
    return applied


def drop_all(engine: Engine) -> None:
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "DROP TABLE IF EXISTS relationships, investigations, correlation_rules, "
            "event_entities, entities, events, schema_migrations CASCADE"
        )
