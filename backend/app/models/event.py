from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    ts: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    user_name: Mapped[str | None] = mapped_column(String(128))
    src_computer: Mapped[str | None] = mapped_column(String(64))
    dst_computer: Mapped[str | None] = mapped_column(String(64))
    attributes: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    raw_line: Mapped[str] = mapped_column(Text, nullable=False)
    source_file: Mapped[str] = mapped_column(String(255), nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    dataset_label: Mapped[str] = mapped_column(String(80), nullable=False)
    dedup_key: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    ingested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    entity_links: Mapped[list["EventEntity"]] = relationship(back_populates="event", lazy="selectin")


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(16), nullable=False)
    value: Mapped[str] = mapped_column(String(128), nullable=False)
    correlatable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class EventEntity(Base):
    __tablename__ = "event_entities"

    event_id: Mapped[int] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    entity_id: Mapped[int] = mapped_column(ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(24), primary_key=True)

    event: Mapped[Event] = relationship(back_populates="entity_links")
    entity: Mapped[Entity] = relationship(lazy="joined")
