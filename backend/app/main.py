"""TRACEVERIFY FastAPI application."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.controllers import events, investigations

app = FastAPI(
    title="TRACEVERIFY API",
    version="1.0.0",
    description="Evidence correlation & cyber-incident verification. Builds explainable candidate incident "
                "timelines with a Hybrid Entity–Temporal–Rule correlation engine. Correlation results are "
                "candidate evidence relationships, not proof of causality.",
)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list,
                   allow_origin_regex=settings.cors_origin_regex or None,
                   allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(OperationalError)
async def database_unavailable(_: Request, exc: OperationalError):
    return JSONResponse(status_code=503, content={"detail": "PostgreSQL is unavailable — is the database running?"})


app.include_router(investigations.router)
app.include_router(events.router)


@app.get("/", include_in_schema=False)
def root():
    return {"name": "TRACEVERIFY API", "docs": "/docs"}
