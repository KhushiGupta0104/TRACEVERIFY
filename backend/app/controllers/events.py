from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.repositories.event_repository import EventRepository
from app.repositories.rule_repository import RuleRepository
from app.schemas.investigation import EntityContextOut, EventDetailOut, RuleOut
from app.services.investigation_service import event_out

router = APIRouter(prefix="/api", tags=["evidence"])


@router.get("/events/{event_id}", response_model=EventDetailOut, summary="Evidence event detail")
def get_event(event_id: int, db: Session = Depends(get_db)):
    repo = EventRepository(db)
    event = repo.get(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail=f"event {event_id} not found")
    process = (event.attributes or {}).get("processName")
    return EventDetailOut(**event_out(event).model_dump(),
                          entities=[EntityContextOut(**c) for c in repo.entity_context(event)],
                          process_rarity=repo.process_rarity(process) if process else None)


@router.get("/rules", response_model=list[RuleOut], summary="Correlation rule registry")
def list_rules(db: Session = Depends(get_db)):
    return [RuleOut(code=r.code, name=r.name, from_types=r.from_types, to_types=r.to_types,
                    condition_text=r.condition_text, full_score=float(r.full_score),
                    partial_score=float(r.partial_score), enabled=r.enabled) for r in RuleRepository(db).list()]


@router.get("/dataset", summary="Evidence store contents by source and provenance label")
def dataset(db: Session = Depends(get_db)):
    return EventRepository(db).dataset_summary()


@router.get("/health", summary="Service and database health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "postgresql"}
