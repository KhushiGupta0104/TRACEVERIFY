"""Explainable Entity / Temporal / Rule scoring.

    FinalScore = w_entity·EntityScore + w_temporal·TemporalScore + w_rule·RuleScore

All component scores lie in [0, 1]; weights are non-negative and sum to 1, so the
final score lies in [0, 1] as well.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.rules.definitions import RULES, RuleDefinition
from app.services.evidence import EvidenceEvent

# Entity-score contributions (documented in README §Scoring)
W_SHARED_USER = 0.45        # at least one shared correlatable user
W_SHARED_COMPUTER = 0.30    # per shared computer, at most two counted
W_HOST_CONTINUITY = 0.25    # later event originates where the earlier event landed
BACKWARD_ORDER_FACTOR = 0.85  # child event precedes its parent (precursor evidence)
WEIGHT_TOLERANCE = 1e-6


def validate_weights(w_entity: float, w_temporal: float, w_rule: float) -> None:
    weights = (w_entity, w_temporal, w_rule)
    if any(w < 0 for w in weights):
        raise ValueError("weights must be non-negative")
    if abs(sum(weights) - 1.0) > WEIGHT_TOLERANCE:
        raise ValueError(f"weights must sum to 1 (got {sum(weights):.4f})")


@dataclass
class EntityResult:
    score: float
    shared: list[dict]                 # [{"type": "user"|"computer", "value": ...}]
    continuity_host: str | None


@dataclass
class RuleResult:
    code: str | None
    name: str | None
    match: str | None                  # full | partial | None
    score: float
    reason: str


@dataclass
class RuleSet:
    """Rule definitions with score/enabled overrides loaded from the database."""
    rules: list[RuleDefinition] = field(default_factory=lambda: list(RULES))
    overrides: dict[str, tuple[float, float, bool]] = field(default_factory=dict)

    def scores(self, rule: RuleDefinition) -> tuple[float, float, bool]:
        return self.overrides.get(rule.code, (rule.full_score, rule.partial_score, True))


def chronological(a: EvidenceEvent, b: EvidenceEvent) -> tuple[EvidenceEvent, EvidenceEvent]:
    """Order a pair by time; ties keep the given (parent, child) order."""
    return (b, a) if b.ts < a.ts else (a, b)


def entity_score(parent: EvidenceEvent, child: EvidenceEvent) -> EntityResult:
    earlier, later = chronological(parent, child)
    users = sorted(parent.users & child.users)
    computers = sorted(parent.computers & child.computers)
    continuity = earlier.target_host if (earlier.target_host and earlier.target_host == later.actor_host) else None
    score = (W_SHARED_USER * bool(users) + W_SHARED_COMPUTER * min(len(computers), 2)
             + W_HOST_CONTINUITY * bool(continuity))
    shared = [{"type": "user", "value": u} for u in users] + [{"type": "computer", "value": c} for c in computers]
    return EntityResult(min(1.0, score), shared, continuity)


def temporal_score(delta_seconds: int, decay_seconds: float) -> float:
    """exp(-|Δt|/τ), multiplied by an ordering factor when the child precedes its parent."""
    proximity = math.exp(-abs(delta_seconds) / decay_seconds)
    return proximity * (1.0 if delta_seconds >= 0 else BACKWARD_ORDER_FACTOR)


def rule_score(parent: EvidenceEvent, child: EvidenceEvent, ruleset: RuleSet) -> RuleResult:
    """Best matching transition rule for the chronologically ordered pair."""
    earlier, later = chronological(parent, child)
    best = RuleResult(None, None, None, 0.0,
                      f"no compatible transition rule for {earlier.event_type} → {later.event_type}")
    for rule in ruleset.rules:
        full, partial, enabled = ruleset.scores(rule)
        if not enabled or earlier.event_type not in rule.from_types or later.event_type not in rule.to_types:
            continue
        match, reason = rule.check(earlier, later)
        score = full if match == "full" else partial if match == "partial" else 0.0
        if match and score > best.score:
            best = RuleResult(rule.code, rule.name, match, score, reason)
        elif best.code is None and not match:
            best.reason = f"{rule.code} {rule.name} not satisfied: {reason}"
    return best


def final_score(e: float, t: float, r: float, w_entity: float, w_temporal: float, w_rule: float) -> float:
    return max(0.0, min(1.0, w_entity * e + w_temporal * t + w_rule * r))
