"""Hybrid Entity–Temporal–Rule correlation engine.

Starting from an investigation seed the engine expands a bounded evidence graph hop by hop:

  1. retrieve candidates that share ≥1 correlatable entity with the current frontier and
     fall inside the investigation window (red-team rows are never candidates);
  2. score every (frontier parent, candidate) pair that actually shares an entity;
  3. keep each candidate's best parent; accept it if FinalScore ≥ threshold, otherwise
     remember its best (rejected) edge for transparency;
  4. accepted candidates become the next frontier.

Edges only ever point from an already-accepted event to a newly accepted event, so the
graph is acyclic and free of duplicate edges. `max_hops` and `max_nodes` bound expansion.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Protocol

from app.services.evidence import EvidenceEvent
from app.services.scoring import (
    EntityResult, RuleResult, RuleSet, entity_score, final_score, rule_score, temporal_score, validate_weights,
)

ALL_SOURCES = ("auth", "proc", "dns", "flow")


@dataclass(frozen=True)
class InvestigationParams:
    window_before: int = 300
    window_after: int = 1800
    threshold: float = 0.60
    w_entity: float = 0.40
    w_temporal: float = 0.30
    w_rule: float = 0.30
    temporal_decay: float = 300.0
    max_hops: int = 3          # bounded expansion rounds
    max_nodes: int = 60
    source_types: tuple[str, ...] = ALL_SOURCES
    max_parents: int = 2  # primary + at most one supporting edge per accepted event

    def validate(self) -> None:
        validate_weights(self.w_entity, self.w_temporal, self.w_rule)
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError("threshold must be within [0, 1]")
        if self.window_before < 0 or self.window_after < 0:
            raise ValueError("window bounds must be non-negative")
        if self.temporal_decay <= 0:
            raise ValueError("temporal_decay must be positive")
        if self.max_hops < 1 or self.max_nodes < 1:
            raise ValueError("max_hops and max_nodes must be ≥ 1")
        unknown = set(self.source_types) - set(ALL_SOURCES)
        if unknown or not self.source_types:
            raise ValueError(f"source_types must be a non-empty subset of {ALL_SOURCES}")

    def window(self, seed_ts: int) -> tuple[int, int]:
        return seed_ts - self.window_before, seed_ts + self.window_after


class CandidateProvider(Protocol):
    def fetch_candidates(self, keys: set[tuple[str, str]], t_min: int, t_max: int,
                         exclude_ids: set[int], source_types: tuple[str, ...]) -> list[EvidenceEvent]: ...

    def count_in_window(self, t_min: int, t_max: int, source_types: tuple[str, ...]) -> int: ...


@dataclass
class ScoredEdge:
    parent: EvidenceEvent
    child: EvidenceEvent
    entity: EntityResult
    temporal: float
    rule: RuleResult
    final: float
    hop: int
    status: str = "rejected"
    is_primary: bool = False
    explanation: str = ""
    over_budget: bool = False

    @property
    def delta(self) -> int:
        return self.child.ts - self.parent.ts

    @property
    def direction(self) -> str:
        return "forward" if self.delta >= 0 else "backward"


@dataclass
class CorrelationResult:
    seed: EvidenceEvent
    hop_of: dict[int, int]
    events: dict[int, EvidenceEvent]
    accepted: list[ScoredEdge]
    rejected: list[ScoredEdge]
    metrics: dict = field(default_factory=dict)


def _fmt_delta(seconds: int) -> str:
    sign = "after" if seconds >= 0 else "before"
    s = abs(seconds)
    text = f"{s}s" if s < 120 else f"{s // 60}m {s % 60:02d}s"
    return f"{text} {sign}"


def explain(edge: ScoredEdge, params: InvestigationParams) -> str:
    p, c = edge.parent, edge.child
    parent_name = "the seed" if p.source_type == "redteam" else f"event #{p.id}"
    parts = [f"{c.event_type} ({c.describe()}) occurs {_fmt_delta(edge.delta)} {parent_name}."]
    if edge.entity.shared:
        shared = ", ".join(f"{s['type']} {s['value']}" for s in edge.entity.shared)
        parts.append(f"Shared entities: {shared}.")
    if edge.entity.continuity_host:
        parts.append(f"Host continuity: activity continues on {edge.entity.continuity_host}.")
    if edge.rule.code:
        parts.append(f"Rule {edge.rule.code} '{edge.rule.name}' matched ({edge.rule.match}): {edge.rule.reason}.")
    else:
        parts.append(f"No transition rule matched — {edge.rule.reason}.")
    verdict = "≥" if edge.final >= params.threshold else "<"
    parts.append(
        f"Scores: entity {edge.entity.score:.2f}, temporal {edge.temporal:.2f}, rule {edge.rule.score:.2f} → "
        f"final {edge.final:.3f} {verdict} threshold {params.threshold:.2f}"
        + (" (excluded: node budget reached)." if edge.over_budget
           else " (accepted)." if verdict == "≥" else " (rejected)."))
    if edge.status == "accepted":
        parts.append("Candidate evidence relationship — correlation does not prove causality or intent.")
    return " ".join(parts)


def score_pair(parent: EvidenceEvent, child: EvidenceEvent, params: InvestigationParams,
               ruleset: RuleSet, hop: int) -> ScoredEdge:
    ent = entity_score(parent, child)
    tmp = temporal_score(child.ts - parent.ts, params.temporal_decay)
    rul = rule_score(parent, child, ruleset)
    fin = final_score(ent.score, tmp, rul.score, params.w_entity, params.w_temporal, params.w_rule)
    return ScoredEdge(parent, child, ent, tmp, rul, fin, hop)


def correlate(seed: EvidenceEvent, provider: CandidateProvider, params: InvestigationParams,
              ruleset: RuleSet | None = None) -> CorrelationResult:
    params.validate()
    ruleset = ruleset or RuleSet()
    t_min, t_max = params.window(seed.ts)

    events: dict[int, EvidenceEvent] = {seed.id: seed}
    discovered: dict[int, ScoredEdge] = {}
    best_rejected: dict[int, ScoredEdge] = {}
    evaluated: set[int] = set()
    pairs_scored = 0
    truncated = 0
    rounds = 0
    frontier = [seed]

    for hop in range(1, params.max_hops + 1):
        if not frontier:
            break
        keys = set().union(*(f.correlation_keys for f in frontier))
        if not keys:
            break
        candidates = provider.fetch_candidates(keys, t_min, t_max, set(events), params.source_types)
        edges_by_child: dict[int, list[ScoredEdge]] = defaultdict(list)
        for cand in candidates:
            if cand.id in events or not (t_min <= cand.ts <= t_max) or cand.source_type == "redteam":
                continue
            evaluated.add(cand.id)
            for parent in frontier:
                if not (parent.correlation_keys & cand.correlation_keys):
                    continue
                edges_by_child[cand.id].append(score_pair(parent, cand, params, ruleset, hop))
                pairs_scored += 1

        winners: list[tuple[ScoredEdge, list[ScoredEdge]]] = []
        for cid, edges in edges_by_child.items():
            edges.sort(key=lambda e: (-e.final, abs(e.delta), e.parent.id))
            good = [e for e in edges if e.final >= params.threshold]
            if good:
                winners.append((good[0], good[1:]))
            elif cid not in best_rejected or edges[0].final > best_rejected[cid].final:
                best_rejected[cid] = edges[0]

        winners.sort(key=lambda w: (-w[0].final, w[0].child.ts, w[0].child.id))
        room = params.max_nodes - (len(events) - 1)
        if len(winners) > room:
            truncated += len(winners) - room
            for primary, _ in winners[room:]:
                primary.over_budget = True
                best_rejected[primary.child.id] = primary
            winners = winners[:max(room, 0)]

        frontier = []
        for primary, _ in winners:
            child = primary.child
            events[child.id] = child
            discovered[child.id] = primary
            best_rejected.pop(child.id, None)
            frontier.append(child)
        if frontier:
            rounds = hop

    accepted, hop_of = _reconstruct_paths(seed, events, discovered, params, ruleset)
    rejected = [e for cid, e in best_rejected.items() if cid not in events]
    for edge in accepted + rejected:
        edge.explanation = explain(edge, params)

    in_window = provider.count_in_window(t_min, t_max, params.source_types)
    metrics = {
        "window": [t_min, t_max],
        "events_in_window": in_window,
        "candidates_evaluated": len(evaluated),
        "pairs_scored": pairs_scored,
        "accepted_events": len(events) - 1,
        "accepted_relationships": len(accepted),
        "rejected_candidates": len(rejected),
        "truncated_by_node_budget": truncated,
        "expansion_rounds": rounds,
        "max_path_depth": max(hop_of.values()),
        "candidate_reduction": round(1 - len(evaluated) / in_window, 4) if in_window else 0.0,
    }
    return CorrelationResult(seed, hop_of, events, accepted, rejected, metrics)


def _is_ancestor(node_id: int, of_id: int, parent: dict[int, int]) -> bool:
    """True if node_id lies on the primary-parent chain above (or is) of_id."""
    cur: int | None = of_id
    while cur is not None:
        if cur == node_id:
            return True
        cur = parent.get(cur)
    return False


def _reconstruct_paths(seed: EvidenceEvent, events: dict[int, EvidenceEvent], discovered: dict[int, ScoredEdge],
                       params: InvestigationParams, ruleset: RuleSet) -> tuple[list[ScoredEdge], dict[int, int]]:
    """Step-based path reconstruction over the accepted event set.

    Inclusion was decided by the bounded expansion. Here each accepted event chooses as its
    primary parent the best-scoring accepted event that precedes it in time (seed first),
    so chains such as logon → process → DNS → flow emerge. If no earlier event reaches the
    threshold, the edge that discovered it is kept. Every assignment is cycle-checked.
    """
    order = [seed] + sorted((e for i, e in events.items() if i != seed.id), key=lambda e: (e.ts, e.id))
    parent_of: dict[int, int] = {}
    primary: dict[int, ScoredEdge] = {}
    candidates_by_child: dict[int, list[ScoredEdge]] = {}

    for idx, child in enumerate(order[1:], start=1):
        edges = sorted((score_pair(p, child, params, ruleset, 0) for p in order[:idx]
                        if p.correlation_keys & child.correlation_keys),
                       key=lambda e: (-e.final, abs(e.delta), e.parent.id))
        good = [e for e in edges if e.final >= params.threshold and not _is_ancestor(child.id, e.parent.id, parent_of)]
        candidates_by_child[child.id] = good
        chosen = good[0] if good else discovered[child.id]
        if _is_ancestor(child.id, chosen.parent.id, parent_of):  # defensive; cannot happen for the seed
            chosen = discovered[child.id]
        primary[child.id] = chosen
        parent_of[child.id] = chosen.parent.id

    hop_of = {seed.id: 0}

    def depth(i: int) -> int:
        if i not in hop_of:
            hop_of[i] = depth(parent_of[i]) + 1
        return hop_of[i]

    accepted: list[ScoredEdge] = []
    for cid, edge in primary.items():
        edge.hop, edge.status, edge.is_primary = depth(cid), "accepted", True
        accepted.append(edge)
    for cid, good in candidates_by_child.items():
        extras = [e for e in good if e.parent.id != primary[cid].parent.id
                  and not _is_ancestor(cid, e.parent.id, parent_of)][: params.max_parents - 1]
        for e in extras:
            e.hop, e.status = hop_of[cid], "accepted"
            accepted.append(e)
    return accepted, hop_of
