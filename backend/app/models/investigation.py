from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.event import Event


class CorrelationRule(Base):
    __tablename__ = "correlation_rules"

    code: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    from_types: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    to_types: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False)
    condition_text: Mapped[str] = mapped_column(Text, nullable=False)
    full_score: Mapped[float] = mapped_column(Numeric(4, 3, asdecimal=False), nullable=False)
    partial_score: Mapped[float] = mapped_column(Numeric(4, 3, asdecimal=False), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class Investigation(Base):
    __tablename__ = "investigations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    seed_event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="completed")
    params: Mapped[dict] = mapped_column(JSONB, nullable=False)
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    run_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    seed_event: Mapped[Event] = relationship(lazy="joined")


class Relationship(Base):
    __tablename__ = "relationships"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    investigation_id: Mapped[int] = mapped_column(ForeignKey("investigations.id", ondelete="CASCADE"))
    source_event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    target_event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False)
    hop: Mapped[int] = mapped_column(Integer, nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)
    time_delta_seconds: Mapped[int] = mapped_column(BigInteger, nullable=False)
    shared_entities: Mapped[list] = mapped_column(JSONB, nullable=False)
    entity_score: Mapped[float] = mapped_column(Numeric(5, 4, asdecimal=False), nullable=False)
    temporal_score: Mapped[float] = mapped_column(Numeric(5, 4, asdecimal=False), nullable=False)
    rule_score: Mapped[float] = mapped_column(Numeric(5, 4, asdecimal=False), nullable=False)
    final_score: Mapped[float] = mapped_column(Numeric(5, 4, asdecimal=False), nullable=False)
    matched_rule_code: Mapped[str | None] = mapped_column(ForeignKey("correlation_rules.code"))
    rule_match: Mapped[str | None] = mapped_column(String(8))
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
