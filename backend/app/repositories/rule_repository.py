"""Correlation-rule registry persistence."""
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.models import CorrelationRule
from app.rules.definitions import RULES
from app.services.scoring import RuleSet


def sync_rules(engine: Engine) -> int:
    """Insert rule definitions that are missing from the registry. Existing rows keep any
    tuned scores / enabled flags; name, types and condition text follow the code."""
    with engine.begin() as conn:
        for r in RULES:
            stmt = insert(CorrelationRule).values(
                code=r.code, name=r.name, from_types=sorted(r.from_types), to_types=sorted(r.to_types),
                condition_text=r.condition_text, full_score=r.full_score, partial_score=r.partial_score,
                enabled=True)
            conn.execute(stmt.on_conflict_do_update(index_elements=["code"], set_={
                "name": stmt.excluded.name, "from_types": stmt.excluded.from_types,
                "to_types": stmt.excluded.to_types, "condition_text": stmt.excluded.condition_text}))
    return len(RULES)


class RuleRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self) -> list[CorrelationRule]:
        return list(self.db.scalars(select(CorrelationRule).order_by(CorrelationRule.code)))

    def load_ruleset(self) -> RuleSet:
        overrides = {r.code: (float(r.full_score), float(r.partial_score), r.enabled) for r in self.list()}
        return RuleSet(overrides=overrides)
