"""Correlation engine behaviour on an in-memory provider."""
import pytest

from app.services.correlation_engine import InvestigationParams, correlate
from tests.conftest import MemoryProvider


def run(chain_events, **kw):
    seed, events = chain_events
    return correlate(seed, MemoryProvider(events), InvestigationParams(**kw))


def accepted_ids(result):
    return set(result.events) - {result.seed.id}


def test_reconstructs_chain_and_excludes_distractors(chain_events):
    res = run(chain_events)
    ids = accepted_ids(res)
    assert {2, 3, 4, 5}.issubset(ids)          # matching logon, process, DNS, flow
    assert 6 not in ids                         # temporal distractor without shared entity
    assert 7 not in ids                         # shares host, far in time, no rule
    assert 8 not in ids                         # failed logon from unrelated hosts


def test_step_chain_parentage(chain_events):
    res = run(chain_events)
    parent = {e.child.id: e.parent.id for e in res.accepted if e.is_primary}
    assert parent[4] == 3                       # process → DNS (R03)
    assert parent[5] == 4                       # DNS → flow (R04)
    assert res.hop_of[3] == 1 and res.hop_of[5] == 3


def test_direct_vs_multi_hop_and_no_cycles(chain_events):
    res = run(chain_events, threshold=0.5)
    primaries = [e for e in res.accepted if e.is_primary]
    assert len({e.child.id for e in primaries}) == len(primaries)        # one primary per event
    edges = [(e.parent.id, e.child.id) for e in res.accepted]
    assert len(edges) == len(set(edges))                                   # no duplicate edges
    parent = {e.child.id: e.parent.id for e in primaries}
    for node in parent:                                                    # every chain ends at the seed
        seen, cur = set(), node
        while cur != res.seed.id:
            assert cur not in seen
            seen.add(cur)
            cur = parent[cur]
    assert any(res.hop_of[e.child.id] == 1 for e in primaries)
    assert any(res.hop_of[e.child.id] > 1 for e in primaries)


@pytest.mark.parametrize("low,high", [(0.3, 0.5), (0.5, 0.6), (0.6, 0.8), (0.4, 0.9)])
def test_lowering_threshold_never_removes_events(chain_events, low, high):
    assert accepted_ids(run(chain_events, threshold=high)) <= accepted_ids(run(chain_events, threshold=low))


def test_threshold_changes_results(chain_events):
    assert len(accepted_ids(run(chain_events, threshold=0.3))) > len(accepted_ids(run(chain_events, threshold=0.9)))


def test_all_accepted_edges_meet_threshold_and_scores_in_range(chain_events):
    res = run(chain_events, threshold=0.6)
    for e in res.accepted:
        assert e.final >= 0.6
        for s in (e.entity.score, e.temporal, e.rule.score, e.final):
            assert 0.0 <= s <= 1.0
        assert e.explanation and "causality" in e.explanation
    for e in res.rejected:
        assert e.final < 0.6 or e.over_budget


def test_narrow_window_excludes_outside_events(chain_events):
    res = run(chain_events, window_before=0, window_after=12, threshold=0.3)
    seed = res.seed
    for eid, e in res.events.items():
        if eid != seed.id:
            assert seed.ts <= e.ts <= seed.ts + 12
    assert 2 not in res.events                  # precursor logon is before the window
    assert 9 not in res.events


def test_source_filter(chain_events):
    res = run(chain_events, source_types=("auth", "proc"))
    assert all(e.source_type in ("auth", "proc") for i, e in res.events.items() if i != 1)


def test_node_budget_bounds_graph(chain_events):
    res = run(chain_events, threshold=0.3, max_nodes=2)
    assert len(res.events) - 1 == 2
    assert res.metrics["truncated_by_node_budget"] > 0


def test_invalid_params_rejected(chain_events):
    with pytest.raises(ValueError):
        run(chain_events, w_entity=0.5, w_temporal=0.5, w_rule=0.5)
    with pytest.raises(ValueError):
        run(chain_events, threshold=1.5)
    with pytest.raises(ValueError):
        run(chain_events, source_types=("redteam",))


def test_deterministic(chain_events):
    a, b = run(chain_events, threshold=0.5), run(chain_events, threshold=0.5)
    assert [(e.parent.id, e.child.id, e.final) for e in a.accepted] == \
           [(e.parent.id, e.child.id, e.final) for e in b.accepted]
