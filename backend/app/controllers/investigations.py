from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.repositories.event_repository import EventRepository
from app.schemas.investigation import (
    InvestigationListItem, InvestigationOut, InvestigationParamsIn, RelationshipOut, RerunInvestigationIn, SeedOut,
    StartInvestigationIn, TimelineEventOut,
)
from app.services.investigation_service import InvestigationService, NotFoundError, event_out

router = APIRouter(prefix="/api/investigations", tags=["investigations"])

SEED_NEARBY_RADIUS = 1800


def _service(db: Session = Depends(get_db)) -> InvestigationService:
    return InvestigationService(db)


def _not_found(exc: NotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


@router.get("/seeds", response_model=list[SeedOut], summary="List red-team investigation seeds")
def list_seeds(db: Session = Depends(get_db)):
    repo = EventRepository(db)
    return [SeedOut(**event_out(e).model_dump(), nearby_evidence=repo.count_nearby(e.ts, SEED_NEARBY_RADIUS))
            for e in repo.list_seeds()]


@router.get("", response_model=list[InvestigationListItem], summary="Recent investigations")
def list_investigations(svc: InvestigationService = Depends(_service)):
    return [InvestigationListItem(id=i.id, seed_event_id=i.seed_event_id, seed_summary=event_out(i.seed_event).summary,
                                  threshold=i.params["threshold"], accepted_events=i.metrics.get("accepted_events", 0),
                                  run_count=i.run_count, updated_at=i.updated_at)
            for i in svc.investigations.list_recent()]


@router.post("/start", response_model=InvestigationOut, status_code=201,
             summary="Start an investigation from a seed event")
def start_investigation(body: StartInvestigationIn, svc: InvestigationService = Depends(_service)):
    params = InvestigationParamsIn(**body.model_dump(exclude={"seed_event_id"}))
    try:
        inv = svc.start(body.seed_event_id, params)
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    return svc.detail(inv)


@router.get("/{investigation_id}", response_model=InvestigationOut, summary="Investigation summary")
def get_investigation(investigation_id: int, svc: InvestigationService = Depends(_service)):
    try:
        return svc.detail(svc.get(investigation_id))
    except NotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/{investigation_id}/events", response_model=list[TimelineEventOut],
            summary="Chronological candidate incident timeline")
def get_timeline(investigation_id: int, include_rejected: bool = Query(False),
                 svc: InvestigationService = Depends(_service)):
    try:
        return svc.timeline(investigation_id, include_rejected)
    except NotFoundError as exc:
        raise _not_found(exc) from exc


@router.get("/{investigation_id}/relationships", response_model=list[RelationshipOut],
            summary="Evidence relationships ranked by FinalScore")
def get_relationships(investigation_id: int,
                      status: Literal["accepted", "rejected", "all"] = Query("accepted"),
                      svc: InvestigationService = Depends(_service)):
    try:
        return svc.relationships(investigation_id, None if status == "all" else status)
    except NotFoundError as exc:
        raise _not_found(exc) from exc


@router.post("/{investigation_id}/rerun", response_model=InvestigationOut,
             summary="Re-run an investigation with changed parameters")
def rerun_investigation(investigation_id: int, body: RerunInvestigationIn | None = None,
                        svc: InvestigationService = Depends(_service)):
    try:
        inv = svc.rerun(investigation_id, body or RerunInvestigationIn())
    except NotFoundError as exc:
        raise _not_found(exc) from exc
    return svc.detail(inv)
