"""Entity / Temporal / Rule / Final scoring."""
import math

import pytest

from app.services.scoring import (
    BACKWARD_ORDER_FACTOR, RuleSet, entity_score, final_score, rule_score, temporal_score, validate_weights,
)
from tests.conftest import ev

SEED = ev(1, 1000, "redteam", "REDTEAM_COMPROMISE", "U1@D", "C1", "C2")


def test_entity_score_full_overlap_is_capped_at_one():
    auth = ev(2, 995, "auth", "AUTH_LOGON", "U1@D", "C1", "C2", outcome="Success")
    res = entity_score(SEED, auth)
    assert res.score == 1.0
    assert {"type": "user", "value": "U1@D"} in res.shared


def test_entity_score_host_continuity():
    dns = ev(3, 1010, "dns", "DNS_RESOLVE", None, "C2", "C9")
    res = entity_score(SEED, dns)
    assert res.continuity_host == "C2"
    assert res.score == pytest.approx(0.30 + 0.25)


def test_entity_score_no_shared_entities():
    other = ev(4, 1001, "proc", "PROC_START", "U9@D", "C7")
    res = entity_score(SEED, other)
    assert res.score == 0 and res.shared == []


def test_temporal_score_decays_and_penalises_backward_order():
    assert temporal_score(0, 300) == 1.0
    assert temporal_score(300, 300) == pytest.approx(math.exp(-1))
    assert temporal_score(-300, 300) == pytest.approx(math.exp(-1) * BACKWARD_ORDER_FACTOR)
    assert temporal_score(10, 300) > temporal_score(100, 300) > temporal_score(1000, 300)


def test_rule_logon_to_process_full_and_partial():
    proc_same_user = ev(5, 1005, "proc", "PROC_START", "U1@D", "C2")
    proc_other_user = ev(6, 1005, "proc", "PROC_START", "U5@D", "C2")
    full = rule_score(SEED, proc_same_user, RuleSet())
    partial = rule_score(SEED, proc_other_user, RuleSet())
    assert (full.code, full.match, full.score) == ("R02", "full", 1.0)
    assert (partial.code, partial.match, partial.score) == ("R02", "partial", 0.5)


def test_rule_requires_chronological_order():
    proc = ev(5, 1005, "proc", "PROC_START", "U1@D", "C2")
    dns_before = ev(6, 1000, "dns", "DNS_RESOLVE", None, "C2", "C9")
    dns_after = ev(7, 1010, "dns", "DNS_RESOLVE", None, "C2", "C9")
    assert rule_score(proc, dns_after, RuleSet()).code == "R03"
    # DNS earlier than the process: DNS→PROC is not a defined transition
    assert rule_score(proc, dns_before, RuleSet()).code is None


def test_rule_dns_to_flow_checks_resolved_host():
    dns = ev(6, 1010, "dns", "DNS_RESOLVE", None, "C2", "C9")
    flow_ok = ev(7, 1012, "flow", "NET_FLOW", None, "C2", "C9")
    flow_other = ev(8, 1012, "flow", "NET_FLOW", None, "C2", "C4")
    assert rule_score(dns, flow_ok, RuleSet()).match == "full"
    assert rule_score(dns, flow_other, RuleSet()).match == "partial"


def test_failed_logon_does_not_satisfy_logon_rules():
    failed = ev(2, 1000, "auth", "AUTH_LOGON", "U1@D", "C1", "C2", outcome="Fail")
    proc = ev(3, 1005, "proc", "PROC_START", "U1@D", "C2")
    res = rule_score(failed, proc, RuleSet())
    assert res.score == 0 and "did not succeed" in res.reason


def test_disabled_rule_override():
    proc = ev(5, 1005, "proc", "PROC_START", "U1@D", "C2")
    rs = RuleSet(overrides={"R02": (1.0, 0.5, False)})
    assert rule_score(SEED, proc, rs).code is None


def test_final_score_weighted_sum():
    assert final_score(1, 0.5, 0, 0.4, 0.3, 0.3) == pytest.approx(0.55)
    assert final_score(1, 1, 1, 0.2, 0.3, 0.5) == pytest.approx(1.0)


@pytest.mark.parametrize("w", [(0.5, 0.5, 0.5), (-0.1, 0.6, 0.5), (0.2, 0.2, 0.2)])
def test_invalid_weights_rejected(w):
    with pytest.raises(ValueError):
        validate_weights(*w)


def test_temporal_proximity_alone_cannot_pass_default_threshold():
    """An event sharing one computer and very close in time but matching no rule must not
    pass the default 0.60 threshold."""
    near = ev(9, 1001, "auth", "AUTH_LOGOFF", "U8@D", "C1", "C5", outcome="Success")
    e = entity_score(SEED, near).score
    t = temporal_score(near.ts - SEED.ts, 300)
    r = rule_score(SEED, near, RuleSet()).score
    assert r == 0
    assert final_score(e, t, r, 0.4, 0.3, 0.3) < 0.60
