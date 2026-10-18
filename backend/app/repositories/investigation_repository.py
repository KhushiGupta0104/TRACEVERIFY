"""Persistence for investigations and their evidence relationships."""
from __future__ import annotations

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import Investigation, Relationship
from app.services.correlation_engine import ScoredEdge


class InvestigationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, investigation_id: int) -> Investigation | None:
        return self.db.get(Investigation, investigation_id)

    def list_recent(self, limit: int = 20) -> list[Investigation]:
        return list(self.db.scalars(select(Investigation).order_by(Investigation.id.desc()).limit(limit)))

    def create(self, seed_event_id: int, params: dict) -> Investigation:
        inv = Investigation(seed_event_id=seed_event_id, params=params, metrics={}, status="completed", run_count=0)
        self.db.add(inv)
        self.db.flush()
        return inv

    def replace_relationships(self, inv: Investigation, edges: list[ScoredEdge]) -> None:
        self.db.execute(delete(Relationship).where(Relationship.investigation_id == inv.id))
        self.db.add_all([Relationship(
            investigation_id=inv.id, source_event_id=e.parent.id, target_event_id=e.child.id,
            status=e.status, is_primary=e.is_primary, hop=e.hop, direction=e.direction,
            time_delta_seconds=e.delta, shared_entities=e.entity.shared + (
                [{"type": "host_continuity", "value": e.entity.continuity_host}] if e.entity.continuity_host else []),
            entity_score=round(e.entity.score, 4), temporal_score=round(e.temporal, 4),
            rule_score=round(e.rule.score, 4), final_score=round(e.final, 4),
            matched_rule_code=e.rule.code, rule_match=e.rule.match, explanation=e.explanation,
        ) for e in edges])

    def relationships(self, investigation_id: int, status: str | None = "accepted") -> list[Relationship]:
        q = select(Relationship).where(Relationship.investigation_id == investigation_id)
        if status:
            q = q.where(Relationship.status == status)
        return list(self.db.scalars(q.order_by(Relationship.final_score.desc(), Relationship.id)))

    def touch(self, inv: Investigation) -> None:
        inv.updated_at = func.now()
