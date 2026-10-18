"""Database access for evidence events and entities."""
from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.models import Entity, Event, EventEntity
from app.services.evidence import EvidenceEvent

# Candidate retrieval: events in the window that share ≥1 correlatable entity with the frontier.
CANDIDATE_SQL = text("""
    SELECT DISTINCT e.id
    FROM event_entities ee
    JOIN entities n ON n.id = ee.entity_id AND n.correlatable
    JOIN events e   ON e.id = ee.event_id
    WHERE (n.entity_type, n.value) IN (SELECT * FROM unnest(CAST(:types AS text[]), CAST(:vals AS text[])))
      AND e.ts BETWEEN :t_min AND :t_max
      AND e.source_type = ANY(CAST(:sources AS text[]))
      AND e.source_type <> 'redteam'
      AND NOT (e.id = ANY(CAST(:exclude AS bigint[])))
    ORDER BY e.id
    LIMIT :limit
""")

MAX_CANDIDATES_PER_HOP = 5000


class EventRepository:
    def __init__(self, db: Session):
        self.db = db

    # ----- lookups ---------------------------------------------------------
    def get(self, event_id: int) -> Event | None:
        return self.db.get(Event, event_id)

    def get_many(self, ids: list[int]) -> dict[int, Event]:
        if not ids:
            return {}
        return {e.id: e for e in self.db.scalars(select(Event).where(Event.id.in_(ids)))}

    def list_seeds(self) -> list[Event]:
        return list(self.db.scalars(select(Event).where(Event.source_type == "redteam").order_by(Event.ts, Event.id)))

    def count_nearby(self, ts: int, radius: int) -> int:
        return self.db.scalar(select(func.count()).select_from(Event).where(
            Event.ts.between(ts - radius, ts + radius), Event.source_type != "redteam")) or 0

    def dataset_summary(self) -> list[dict]:
        rows = self.db.execute(select(Event.source_type, Event.dataset_label, func.count(), func.min(Event.ts),
                                      func.max(Event.ts)).group_by(Event.source_type, Event.dataset_label)
                               .order_by(Event.source_type))
        return [{"source_type": r[0], "dataset_label": r[1], "count": r[2], "min_ts": r[3], "max_ts": r[4]}
                for r in rows]

    def entity_context(self, event: Event) -> list[dict]:
        """Frequency context for each entity of an event (supporting information only;
        never used in correlation scoring)."""
        ctx = []
        for link in sorted(event.entity_links, key=lambda l: (l.entity.entity_type, l.role)):
            n = link.entity
            total = self.db.scalar(select(func.count(func.distinct(EventEntity.event_id)))
                                   .where(EventEntity.entity_id == n.id)) or 0
            ctx.append({"entity_type": n.entity_type, "value": n.value, "role": link.role,
                        "correlatable": n.correlatable, "events_with_entity": total})
        return ctx

    def process_rarity(self, process_name: str) -> dict:
        total = self.db.scalar(select(func.count()).select_from(Event).where(Event.source_type == "proc")) or 0
        same = self.db.scalar(select(func.count()).select_from(Event).where(
            Event.source_type == "proc", Event.attributes["processName"].astext == process_name)) or 0
        return {"process": process_name, "occurrences": same, "process_events": total,
                "frequency": round(same / total, 4) if total else 0.0}

    # ----- conversion for the engine ----------------------------------------
    def to_evidence(self, rows: list[Event]) -> list[EvidenceEvent]:
        if not rows:
            return []
        ids = [r.id for r in rows]
        keys: dict[int, dict[str, set[str]]] = defaultdict(lambda: {"user": set(), "computer": set()})
        q = (select(EventEntity.event_id, Entity.entity_type, Entity.value)
             .join(Entity, Entity.id == EventEntity.entity_id)
             .where(EventEntity.event_id.in_(ids), Entity.correlatable,
                    Entity.entity_type.in_(("user", "computer"))))
        for eid, etype, value in self.db.execute(q):
            keys[eid][etype].add(value)
        return [EvidenceEvent(
            id=r.id, ts=r.ts, source_type=r.source_type, event_type=r.event_type, user_name=r.user_name,
            src_computer=r.src_computer, dst_computer=r.dst_computer, attributes=dict(r.attributes or {}),
            users=frozenset(keys[r.id]["user"]), computers=frozenset(keys[r.id]["computer"]),
        ) for r in rows]


class DbCandidateProvider:
    """CandidateProvider backed by PostgreSQL (indexed entity + timestamp lookup)."""

    def __init__(self, db: Session):
        self.repo = EventRepository(db)
        self.db = db

    def fetch_candidates(self, keys, t_min, t_max, exclude_ids, source_types) -> list[EvidenceEvent]:
        if not keys:
            return []
        key_list = sorted(keys)
        ids = [row[0] for row in self.db.execute(CANDIDATE_SQL, {
            "types": [k[0] for k in key_list], "vals": [k[1] for k in key_list],
            "t_min": t_min, "t_max": t_max, "sources": list(source_types),
            "exclude": sorted(exclude_ids), "limit": MAX_CANDIDATES_PER_HOP,
        })]
        rows = self.repo.get_many(ids)
        return self.repo.to_evidence([rows[i] for i in sorted(rows, key=lambda i: (rows[i].ts, i))])

    def count_in_window(self, t_min, t_max, source_types) -> int:
        return self.db.scalar(select(func.count()).select_from(Event).where(
            Event.ts.between(t_min, t_max), Event.source_type.in_(list(source_types)))) or 0
