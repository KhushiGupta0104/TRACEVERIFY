"""Shared fixtures.

Unit tests use an in-memory CandidateProvider. Integration tests use the PostgreSQL
database named by TEST_DATABASE_URL (never the main database); they are skipped if it
is not configured or not reachable.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy.orm import sessionmaker

from app.config import PROJECT_ROOT, settings
from app.services.evidence import EvidenceEvent

DATA_DIR = PROJECT_ROOT / "data"


class MemoryProvider:
    """CandidateProvider over a list of EvidenceEvents (same contract as the DB provider)."""

    def __init__(self, events: list[EvidenceEvent]):
        self.events = events

    def fetch_candidates(self, keys, t_min, t_max, exclude_ids, source_types):
        return sorted((e for e in self.events
                       if e.id not in exclude_ids and t_min <= e.ts <= t_max and e.source_type in source_types
                       and e.source_type != "redteam" and e.correlation_keys & keys),
                      key=lambda e: (e.ts, e.id))

    def count_in_window(self, t_min, t_max, source_types):
        return sum(1 for e in self.events if t_min <= e.ts <= t_max and e.source_type in source_types)


def ev(id, ts, source, etype, user=None, src=None, dst=None, **attrs) -> EvidenceEvent:
    users = frozenset({user} if user and "$" not in user else set())
    computers = frozenset(c for c in (src, dst) if c)
    return EvidenceEvent(id, ts, source, etype, user, src, dst, attrs, users, computers)


@pytest.fixture
def chain_events() -> tuple[EvidenceEvent, list[EvidenceEvent]]:
    """A miniature investigation: seed, a coherent chain, and distractors."""
    seed = ev(1, 1000, "redteam", "REDTEAM_COMPROMISE", "U1@D", "C1", "C2")
    events = [
        ev(2, 995, "auth", "AUTH_LOGON", "U1@D", "C1", "C2", outcome="Success", authOrient="LogOn"),
        ev(3, 1005, "proc", "PROC_START", "U1@D", "C2", processName="powershell.exe"),
        ev(4, 1010, "dns", "DNS_RESOLVE", None, "C2", "C9"),
        ev(5, 1015, "flow", "NET_FLOW", None, "C2", "C9", dstPort="443"),
        # temporal distractor: very close in time, no shared entity
        ev(6, 1006, "proc", "PROC_START", "U7@D", "C5", processName="chrome.exe"),
        # shares host C2 but is far away in time and matches no rule from the chain
        ev(7, 2500, "auth", "AUTH_LOGOFF", "U8@D", "C4", "C2", outcome="Success", authOrient="LogOff"),
        # shares user, failed logon from an unrelated host
        ev(8, 1100, "auth", "AUTH_LOGON", "U1@D", "C6", "C7", outcome="Fail", authOrient="LogOn"),
        # next hop: onward logon from compromised host C2 a few minutes later
        ev(9, 1200, "auth", "AUTH_LOGON", "U1@D", "C2", "C3", outcome="Success", authOrient="LogOn"),
        ev(10, 1210, "proc", "PROC_START", "U1@D", "C3", processName="cmd.exe"),
    ]
    return seed, events


# ---------------------------------------------------------------------------
# PostgreSQL integration fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session")
def pg_engine():
    url = settings.test_database_url
    if not url:
        pytest.skip("TEST_DATABASE_URL not configured")
    if url == settings.database_url:
        pytest.skip("TEST_DATABASE_URL must differ from DATABASE_URL")
    from sqlalchemy import text

    from app.database.migrate import apply_migrations, drop_all
    from app.database.session import make_engine
    from app.repositories.rule_repository import sync_rules

    engine = make_engine(url)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"test database unreachable: {exc.__class__.__name__}")
    drop_all(engine)
    apply_migrations(engine)
    sync_rules(engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def ingested(pg_engine):
    from app.services.ingestion.ingest_service import REDTEAM_LABEL, SYNTHETIC_LABEL, ingest_file

    results = [ingest_file(pg_engine, DATA_DIR / "raw" / "redteam_seed_subset.txt.gz", REDTEAM_LABEL)]
    for name in ("auth.txt.gz", "proc.txt.gz", "dns.txt.gz", "flows.txt.gz"):
        results.append(ingest_file(pg_engine, DATA_DIR / "synthetic" / name, SYNTHETIC_LABEL))
    return results


@pytest.fixture
def db_session(pg_engine, ingested):
    session = sessionmaker(bind=pg_engine, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture
def client(pg_engine, ingested):
    from fastapi.testclient import TestClient

    from app.database.session import get_db
    from app.main import app

    factory = sessionmaker(bind=pg_engine, expire_on_commit=False)

    def _get_db():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def write_lines(path: Path, lines: list[str], gz: bool = False) -> Path:
    import gzip
    data = "\n".join(lines) + "\n"
    if gz:
        with gzip.open(path, "wt", encoding="utf-8") as fh:
            fh.write(data)
    else:
        path.write_text(data, encoding="utf-8")
    return path
