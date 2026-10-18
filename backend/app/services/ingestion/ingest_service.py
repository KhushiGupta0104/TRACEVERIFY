"""Batch ingestion of LANL-format files into PostgreSQL.

Ingestion is idempotent: every row gets a dedup_key = sha1(source | raw line | occurrence),
where occurrence counts identical lines earlier in the same file (real LANL files contain
legitimate identical rows). Re-ingesting the same file therefore inserts nothing new.
"""
from __future__ import annotations

import hashlib
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select, text, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from app.models import Entity, Event, EventEntity
from app.services.ingestion.normalizer import NormalizedEvent, normalize
from app.services.ingestion.parsers import ParseReport, detect_source_type, iter_records

SYNTHETIC_LABEL = "SYNTHETIC / LANL-FORMAT-COMPATIBLE DATA"
LANL_LABEL = "LANL CYBER1 (REAL)"
REDTEAM_LABEL = "LANL RED-TEAM SEED"
BATCH_SIZE = 2000


@dataclass
class TimeFilter:
    """Investigation-window extraction: keep rows inside [t_min, t_max] and, if given,
    within `radius` seconds of any red-team seed time."""
    t_min: int | None = None
    t_max: int | None = None
    seed_times: list[int] = field(default_factory=list)
    radius: int | None = None

    def accepts(self, ts: int) -> bool:
        if self.t_min is not None and ts < self.t_min:
            return False
        if self.t_max is not None and ts > self.t_max:
            return False
        if self.radius is not None and self.seed_times:
            return any(abs(ts - s) <= self.radius for s in self.seed_times)
        return True


@dataclass
class IngestResult:
    path: str
    source_type: str
    label: str
    report: ParseReport
    filtered_out: int = 0
    inserted: int = 0
    duplicates: int = 0


def dedup_key(source_type: str, raw_line: str, occurrence: int) -> str:
    return hashlib.sha1(f"{source_type}|{raw_line}|{occurrence}".encode()).hexdigest()


class EntityCache:
    def __init__(self) -> None:
        self.ids: dict[tuple[str, str], int] = {}

    def resolve(self, conn, refs: Iterable[tuple[str, str, bool]]) -> None:
        missing = {(t, v): c for t, v, c in refs if (t, v) not in self.ids}
        if not missing:
            return
        rows = [{"entity_type": t, "value": v, "correlatable": c} for (t, v), c in missing.items()]
        conn.execute(insert(Entity).values(rows).on_conflict_do_nothing(
            index_elements=["entity_type", "value"]))
        keys = list(missing)
        for i in range(0, len(keys), 1000):
            chunk = keys[i:i + 1000]
            found = conn.execute(select(Entity.id, Entity.entity_type, Entity.value)
                                 .where(tuple_(Entity.entity_type, Entity.value).in_(chunk)))
            for eid, etype, value in found:
                self.ids[(etype, value)] = eid


def _flush(conn, batch: list[tuple[NormalizedEvent, str]], label: str, source_file: str,
           cache: EntityCache) -> int:
    rows = [{
        "ts": ev.ts, "source_type": ev.source_type, "event_type": ev.event_type,
        "user_name": ev.user_name, "src_computer": ev.src_computer, "dst_computer": ev.dst_computer,
        "attributes": ev.attributes, "raw_line": ev.raw_line, "source_file": source_file,
        "line_no": ev.line_no, "dataset_label": label, "dedup_key": key,
    } for ev, key in batch]
    inserted = conn.execute(insert(Event).values(rows).on_conflict_do_nothing(
        index_elements=["dedup_key"]).returning(Event.id, Event.dedup_key)).all()
    if not inserted:
        return 0
    id_by_key = {k: i for i, k in inserted}
    cache.resolve(conn, {(r.entity_type, r.value, r.correlatable) for ev, _ in batch for r in ev.entities})
    links = {(id_by_key[key], cache.ids[(r.entity_type, r.value)], r.role)
             for ev, key in batch if key in id_by_key for r in ev.entities}
    if links:
        conn.execute(insert(EventEntity).values(
            [{"event_id": e, "entity_id": n, "role": role} for e, n, role in links]
        ).on_conflict_do_nothing())
    return len(inserted)


def ingest_file(engine: Engine, path: Path, label: str, time_filter: TimeFilter | None = None,
                source_type: str | None = None) -> IngestResult:
    source_type = source_type or detect_source_type(path)
    if source_type is None:
        raise ValueError(f"Cannot infer LANL source type from file name: {path.name}")
    report = ParseReport(source_type, str(path))
    result = IngestResult(str(path), source_type, label, report)
    seen: Counter[str] = Counter()
    cache = EntityCache()
    batch: list[tuple[NormalizedEvent, str]] = []
    with engine.begin() as conn:
        for record in iter_records(path, source_type, report):
            occurrence = seen[record.raw_line]
            seen[record.raw_line] += 1
            if time_filter and not time_filter.accepts(int(record.fields["time"])):  # type: ignore[arg-type]
                result.filtered_out += 1
                continue
            batch.append((normalize(record), dedup_key(source_type, record.raw_line, occurrence)))
            if len(batch) >= BATCH_SIZE:
                result.inserted += _flush(conn, batch, label, path.name, cache)
                batch = []
        if batch:
            result.inserted += _flush(conn, batch, label, path.name, cache)
    result.duplicates = report.parsed - result.filtered_out - result.inserted
    return result


def read_seed_times(path: Path) -> list[int]:
    report = ParseReport("redteam", str(path))
    return [int(r.fields["time"]) for r in iter_records(path, "redteam", report)]  # type: ignore[arg-type]


def dataset_counts(engine: Engine) -> list[dict]:
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT source_type, dataset_label, count(*), min(ts), max(ts) FROM events "
            "GROUP BY source_type, dataset_label ORDER BY source_type"))
        return [{"source_type": r[0], "dataset_label": r[1], "count": r[2], "min_ts": r[3], "max_ts": r[4]}
                for r in rows]
