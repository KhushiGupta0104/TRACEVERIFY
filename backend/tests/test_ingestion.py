"""Parsing, missing-value handling and normalization (no database required)."""
import pytest

from app.services.ingestion.normalizer import is_correlatable_user, normalize
from app.services.ingestion.parsers import (
    MalformedRecord, ParseReport, detect_source_type, iter_records, parse_line,
)
from tests.conftest import DATA_DIR, write_lines


def test_detect_source_type_from_lanl_names(tmp_path):
    assert detect_source_type(tmp_path / "auth.txt.gz") == "auth"
    assert detect_source_type(tmp_path / "flows.txt") == "flow"
    assert detect_source_type(tmp_path / "redteam_seed_subset.txt.gz") == "redteam"
    assert detect_source_type(tmp_path / "proc_window1.txt") == "proc"
    assert detect_source_type(tmp_path / "notes.txt") is None


def test_parse_auth_with_missing_values():
    rec = parse_line("auth", "100111,U136@DOM1,C146$@DOM1,C152,C5693,?,?,LogOn,Success\n", 4)
    assert rec.fields["time"] == 100111
    assert rec.fields["authType"] is None and rec.fields["logonType"] is None
    assert rec.fields["authOrient"] == "LogOn"


def test_parse_flow_numeric_fields_and_unknown_port():
    rec = parse_line("flow", "100017,14,C174,445,C171,?,6,80,359", 1)
    assert rec.fields["duration"] == 14 and rec.fields["protocol"] == 6
    assert rec.fields["dstPort"] is None and rec.fields["srcPort"] == "445"


@pytest.mark.parametrize("line", [
    "100,C1,C2",                  # too few fields for flow
    "abc,1,C1,1,C2,1,6,1,1",       # non-integer time
    "?,1,C1,1,C2,1,6,1,1",         # missing time
])
def test_malformed_rows_raise(line):
    with pytest.raises(MalformedRecord):
        parse_line("flow", line, 1)


def test_iter_records_skips_malformed_and_reads_gz(tmp_path):
    path = write_lines(tmp_path / "dns.txt.gz", ["1,C1,C2", "bad-row", "", "3,C3,?"], gz=True)
    report = ParseReport("dns", str(path))
    records = list(iter_records(path, "dns", report))
    assert [r.fields["time"] for r in records] == [1, 3]
    assert report.parsed == 2 and report.malformed == 1 and report.total_lines == 3
    assert records[1].fields["resolvedComputer"] is None


def test_normalize_auth_entities_and_machine_accounts():
    ev = normalize(parse_line("auth", "5,U1@DOM1,C9$@DOM1,c1,C2,Kerberos,Network,LogOn,Success", 1))
    assert ev.event_type == "AUTH_LOGON" and ev.src_computer == "C1"  # computers upper-cased
    roles = {(e.role, e.value, e.correlatable) for e in ev.entities}
    assert ("dst_user", "C9$@DOM1", False) in roles  # machine account stored, not a correlation key
    assert ("src_user", "U1@DOM1", True) in roles
    assert ev.attributes["authType"] == "Kerberos"


def test_normalize_proc_dns_flow_redteam():
    proc = normalize(parse_line("proc", "7,U2@DOM1,C3,PowerShell.exe,Start", 1))
    assert (proc.event_type, proc.src_computer, proc.attributes["processName"]) == ("PROC_START", "C3", "powershell.exe")
    assert any(e.entity_type == "process" and not e.correlatable for e in proc.entities)
    dns = normalize(parse_line("dns", "8,C3,C901", 1))
    assert (dns.event_type, dns.src_computer, dns.dst_computer) == ("DNS_RESOLVE", "C3", "C901")
    flow = normalize(parse_line("flow", "9,12,C3,49152,C901,443,6,18,2840", 1))
    assert flow.event_type == "NET_FLOW" and flow.attributes["bytes"] == 2840
    red = normalize(parse_line("redteam", "150885,U620@DOM1,C17693,C1003", 1))
    assert red.event_type == "REDTEAM_COMPROMISE" and red.dst_computer == "C1003"


def test_correlatable_user_rules():
    assert is_correlatable_user("U620@DOM1")
    assert not is_correlatable_user("C152$@DOM1")
    assert not is_correlatable_user("ANONYMOUS LOGON@C586")


def test_supplied_dataset_parses_cleanly():
    for name, source, expected in [("auth.txt.gz", "auth", 244), ("proc.txt.gz", "proc", 260),
                                   ("dns.txt.gz", "dns", 192), ("flows.txt.gz", "flow", 216)]:
        report = ParseReport(source, name)
        assert len(list(iter_records(DATA_DIR / "synthetic" / name, source, report))) == expected
        assert report.malformed == 0
    report = ParseReport("redteam", "seed")
    assert len(list(iter_records(DATA_DIR / "raw" / "redteam_seed_subset.txt.gz", "redteam", report))) == 12
