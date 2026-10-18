"""In-memory evidence representation used by the correlation engine.

Decoupled from SQLAlchemy so the engine can be unit-tested with plain objects and
fed from any CandidateProvider (PostgreSQL in production)."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EvidenceEvent:
    id: int
    ts: int
    source_type: str
    event_type: str
    user_name: str | None = None
    src_computer: str | None = None
    dst_computer: str | None = None
    attributes: dict = field(default_factory=dict, hash=False, compare=False)
    users: frozenset[str] = frozenset()       # correlatable user entities
    computers: frozenset[str] = frozenset()   # correlatable computer entities

    @property
    def actor_host(self) -> str | None:
        """Host where the activity originates (auth/flow/dns source, process host)."""
        return self.src_computer

    @property
    def target_host(self) -> str | None:
        """Host where the activity lands (auth/flow destination, DNS-resolved host, process host)."""
        return self.dst_computer or self.src_computer

    @property
    def correlation_keys(self) -> set[tuple[str, str]]:
        return {("user", u) for u in self.users} | {("computer", c) for c in self.computers}

    def describe(self) -> str:
        a = self.attributes
        if self.source_type == "proc":
            return f"{a.get('processName') or '?'} {self.event_type.split('_')[-1].lower()} on {self.src_computer} by {self.user_name}"
        if self.source_type == "dns":
            return f"{self.src_computer} resolved {self.dst_computer}"
        if self.source_type == "flow":
            return f"flow {self.src_computer} → {self.dst_computer}:{a.get('dstPort') or '?'}"
        if self.source_type == "auth":
            return f"{a.get('authOrient') or 'auth'} {self.user_name} {self.src_computer} → {self.dst_computer} ({a.get('outcome') or '?'})"
        if self.source_type == "redteam":
            return f"red-team seed {self.user_name} {self.src_computer} → {self.dst_computer}"
        return self.event_type


def logon_succeeded(ev: EvidenceEvent) -> bool:
    if ev.source_type == "redteam":
        return True
    return (ev.attributes.get("outcome") or "").lower() == "success"
