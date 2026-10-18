"""Normalization of parsed LANL records into the common investigative representation."""
from __future__ import annotations

from dataclasses import dataclass, field

from app.rules.event_types import auth_event_type, proc_event_type
from app.services.ingestion.parsers import ParsedRecord

NON_INVESTIGATIVE_USERS = {"ANONYMOUS LOGON", "SYSTEM", "LOCAL SERVICE", "NETWORK SERVICE"}


@dataclass(frozen=True)
class EntityRef:
    entity_type: str  # user | computer | process
    value: str
    role: str
    correlatable: bool


@dataclass
class NormalizedEvent:
    ts: int
    source_type: str
    event_type: str
    user_name: str | None
    src_computer: str | None
    dst_computer: str | None
    attributes: dict
    raw_line: str
    line_no: int
    entities: list[EntityRef] = field(default_factory=list)


def normalize_user(value: object) -> str | None:
    if value is None:
        return None
    return str(value).strip() or None


def is_correlatable_user(user: str) -> bool:
    """Machine accounts (C123$@DOM1) and built-in principals are shared by many unrelated
    sessions, so they are stored but not used as correlation keys."""
    account = user.split("@", 1)[0]
    return not account.endswith("$") and account.upper() not in NON_INVESTIGATIVE_USERS


def normalize_computer(value: object) -> str | None:
    if value is None:
        return None
    return str(value).strip().upper() or None


def _user_ref(value: str | None, role: str) -> list[EntityRef]:
    return [EntityRef("user", value, role, is_correlatable_user(value))] if value else []


def _computer_ref(value: str | None, role: str) -> list[EntityRef]:
    return [EntityRef("computer", value, role, True)] if value else []


def normalize(record: ParsedRecord) -> NormalizedEvent:
    f = record.fields
    st = record.source_type
    ts = int(f["time"])  # type: ignore[arg-type]

    if st == "auth":
        src_user, dst_user = normalize_user(f["srcUser"]), normalize_user(f["dstUser"])
        src, dst = normalize_computer(f["srcComputer"]), normalize_computer(f["dstComputer"])
        attrs = {"srcUser": src_user, "dstUser": dst_user, "authType": f["authType"],
                 "logonType": f["logonType"], "authOrient": f["authOrient"], "outcome": f["outcome"]}
        ev = NormalizedEvent(ts, st, auth_event_type(f["authOrient"]), src_user, src, dst, attrs,
                             record.raw_line, record.line_no)
        ev.entities = (_user_ref(src_user, "src_user") + _user_ref(dst_user, "dst_user")
                       + _computer_ref(src, "src_computer") + _computer_ref(dst, "dst_computer"))
    elif st == "proc":
        user, host = normalize_user(f["user"]), normalize_computer(f["computer"])
        process = (str(f["processName"]).strip().lower() if f["processName"] else None)
        attrs = {"processName": process, "eventType": f["eventType"]}
        ev = NormalizedEvent(ts, st, proc_event_type(f["eventType"]), user, host, None, attrs,
                             record.raw_line, record.line_no)
        ev.entities = _user_ref(user, "user") + _computer_ref(host, "computer")
        if process:
            ev.entities.append(EntityRef("process", process, "process", False))
    elif st == "dns":
        src, resolved = normalize_computer(f["srcComputer"]), normalize_computer(f["resolvedComputer"])
        ev = NormalizedEvent(ts, st, "DNS_RESOLVE", None, src, resolved, {"resolvedComputer": resolved},
                             record.raw_line, record.line_no)
        ev.entities = _computer_ref(src, "src_computer") + _computer_ref(resolved, "resolved_computer")
    elif st == "flow":
        src, dst = normalize_computer(f["srcComputer"]), normalize_computer(f["dstComputer"])
        attrs = {k: f[k] for k in ("duration", "srcPort", "dstPort", "protocol", "packets", "bytes")}
        ev = NormalizedEvent(ts, st, "NET_FLOW", None, src, dst, attrs, record.raw_line, record.line_no)
        ev.entities = _computer_ref(src, "src_computer") + _computer_ref(dst, "dst_computer")
    elif st == "redteam":
        user = normalize_user(f["user"])
        src, dst = normalize_computer(f["srcComputer"]), normalize_computer(f["dstComputer"])
        ev = NormalizedEvent(ts, st, "REDTEAM_COMPROMISE", user, src, dst, {}, record.raw_line, record.line_no)
        ev.entities = _user_ref(user, "user") + _computer_ref(src, "src_computer") + _computer_ref(dst, "dst_computer")
    else:  # pragma: no cover - guarded by parser
        raise ValueError(f"unknown source type {st}")
    return ev
