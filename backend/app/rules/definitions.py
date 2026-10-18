"""Explicit event-transition compatibility rules.

Each rule is evaluated on a chronologically ordered pair (earlier A, later B). A rule
matches *fully* when its complete entity condition holds on the actual fields, *partially*
when only a weaker part holds, and not at all otherwise. Rules never consider time
proximity — that is the Temporal Score's job — so a rule cannot accept an event merely
because it happened close to another.

The scores below are defaults; they are copied into the `correlation_rules` table, where
`full_score`, `partial_score` and `enabled` may be tuned without code changes.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from app.services.evidence import EvidenceEvent, logon_succeeded

LOGON = frozenset({"AUTH_LOGON", "REDTEAM_COMPROMISE"})
AUTH_LOGON = frozenset({"AUTH_LOGON"})
SEED = frozenset({"REDTEAM_COMPROMISE"})
PROC_START = frozenset({"PROC_START"})
DNS = frozenset({"DNS_RESOLVE"})
FLOW = frozenset({"NET_FLOW"})
LOGOFF = frozenset({"AUTH_LOGOFF"})

# A check returns ("full" | "partial" | None, reason-text)
Check = Callable[[EvidenceEvent, EvidenceEvent], tuple[str | None, str]]


@dataclass(frozen=True)
class RuleDefinition:
    code: str
    name: str
    from_types: frozenset[str]
    to_types: frozenset[str]
    condition_text: str
    full_score: float
    partial_score: float
    check: Check


def _same_user(a: EvidenceEvent, b: EvidenceEvent) -> bool:
    return bool(a.user_name) and a.user_name == b.user_name


def _r01(a, b):
    if a.event_type in SEED and b.event_type in SEED:
        return None, "both events are seeds"
    if (a.src_computer, a.dst_computer) == (b.src_computer, b.dst_computer) and _same_user(a, b):
        return "full", f"same user {a.user_name} and same path {a.src_computer} → {a.dst_computer}"
    if a.dst_computer == b.dst_computer and _same_user(a, b):
        return "partial", f"same user {a.user_name} logging on to {a.dst_computer}"
    return None, "user/hosts differ from the seed logon"


def _r02(a, b):
    if not logon_succeeded(a):
        return None, "logon did not succeed"
    if b.src_computer == a.dst_computer and _same_user(a, b):
        return "full", f"{b.user_name} starts a process on {b.src_computer}, the logon destination"
    if b.src_computer == a.dst_computer:
        return "partial", f"process starts on logon destination {b.src_computer} under a different user"
    return None, "process host is not the logon destination"


def _r03(a, b):
    if b.src_computer == a.src_computer:
        return "full", f"DNS lookup issued from {b.src_computer}, where the process ran"
    return None, "DNS lookup not issued from the process host"


def _r04(a, b):
    if b.src_computer == a.src_computer and b.dst_computer == a.dst_computer:
        return "full", f"flow from {b.src_computer} to {b.dst_computer}, the host it just resolved"
    if b.src_computer == a.src_computer:
        return "partial", f"flow from the resolving host {b.src_computer} but to another destination"
    return None, "flow does not originate from the resolving host"


def _r05(a, b):
    if not logon_succeeded(a):
        return None, "logon did not succeed"
    if b.src_computer == a.dst_computer:
        return "full", f"outbound flow from logon destination {b.src_computer}"
    if {b.src_computer, b.dst_computer} == {a.src_computer, a.dst_computer}:
        return "partial", "flow between the same two hosts as the logon"
    return None, "flow not related to the logon hosts"


def _r06(a, b):
    if b.src_computer == a.src_computer:
        return "full", f"outbound flow from {b.src_computer}, where the process ran"
    return None, "flow not from the process host"


def _r07(a, b):
    if not logon_succeeded(a):
        return None, "logon did not succeed"
    if b.src_computer == a.dst_computer:
        return "full", f"DNS lookup from logon destination {b.src_computer}"
    return None, "DNS lookup not from the logon destination"


def _r08(a, b):
    if not logon_succeeded(a) or not logon_succeeded(b):
        return None, "one of the logons did not succeed"
    if b.src_computer == a.dst_computer and _same_user(a, b):
        return "full", f"{b.user_name} logs on onward from {b.src_computer}, the previous logon destination"
    if b.src_computer == a.dst_computer:
        return "partial", f"onward logon from {b.src_computer} by a different user"
    if _same_user(a, b) and b.src_computer == a.src_computer:
        return "partial", f"{b.user_name} fans out from the same source host {b.src_computer}"
    return None, "no host continuity between the logons"


def _r09(a, b):
    if b.src_computer == a.src_computer and _same_user(a, b):
        return "full", f"process sequence by {b.user_name} on {b.src_computer}"
    if b.src_computer == a.src_computer:
        return "partial", f"processes on the same host {b.src_computer} by different users"
    return None, "processes on different hosts"


def _r10(a, b):
    if b.src_computer == a.src_computer and _same_user(a, b):
        return "full", f"{b.user_name} authenticates outbound from {b.src_computer} after the process"
    return None, "logon not from the process host by the same user"


def _r11(a, b):
    if (a.src_computer, a.dst_computer) == (b.src_computer, b.dst_computer):
        return "full", f"repeated communication {b.src_computer} → {b.dst_computer}"
    return None, "different host pair"


def _r12(a, b):
    if (a.src_computer, a.dst_computer) == (b.src_computer, b.dst_computer) and _same_user(a, b):
        return "full", f"logoff closes the {b.user_name} session {b.src_computer} → {b.dst_computer}"
    return None, "logoff belongs to a different session"


RULES: list[RuleDefinition] = [
    RuleDefinition("R01", "Seed ↔ same-path authentication", SEED | AUTH_LOGON, SEED | AUTH_LOGON,
                   "One side is the red-team seed; the authentication uses the same user over the same src→dst path (partial: same user and destination). Proximity is judged by the Temporal Score, not by this rule.",
                   1.0, 0.6, _r01),
    RuleDefinition("R02", "Logon → process start on destination host", LOGON, PROC_START,
                   "Successful logon; process host = logon destination and same user (partial: host only).",
                   1.0, 0.5, _r02),
    RuleDefinition("R03", "Process → DNS lookup from same host", PROC_START, DNS,
                   "DNS source computer = process host.", 1.0, 0.0, _r03),
    RuleDefinition("R04", "DNS resolution → flow to resolved host", DNS, FLOW,
                   "Flow source = DNS source and flow destination = resolved computer (partial: source only).",
                   1.0, 0.4, _r04),
    RuleDefinition("R05", "Logon → network flow from destination host", LOGON, FLOW,
                   "Successful logon; flow source = logon destination (partial: flow between the same two hosts).",
                   0.8, 0.4, _r05),
    RuleDefinition("R06", "Process → outbound flow from same host", PROC_START, FLOW,
                   "Flow source = process host.", 0.8, 0.0, _r06),
    RuleDefinition("R07", "Logon → DNS lookup from destination host", LOGON, DNS,
                   "Successful logon; DNS source = logon destination.", 0.7, 0.0, _r07),
    RuleDefinition("R08", "Onward logon from compromised host", LOGON, AUTH_LOGON,
                   "Both logons succeed; second logon originates at the first logon's destination with the same user "
                   "(partial: different user, or same user fanning out from the same source).", 1.0, 0.5, _r08),
    RuleDefinition("R09", "Process sequence on same host", PROC_START, PROC_START,
                   "Same host and same user (partial: same host only).", 0.8, 0.3, _r09),
    RuleDefinition("R10", "Process → outbound logon from same host", PROC_START, AUTH_LOGON,
                   "Logon source = process host and same user.", 0.7, 0.0, _r10),
    RuleDefinition("R11", "Repeated flow between same host pair", FLOW, FLOW,
                   "Identical source and destination computers.", 0.6, 0.0, _r11),
    RuleDefinition("R12", "Logon → logoff of the same session", LOGON, LOGOFF,
                   "Same user and same src→dst path.", 0.5, 0.0, _r12),
]

RULES_BY_CODE = {r.code: r for r in RULES}
