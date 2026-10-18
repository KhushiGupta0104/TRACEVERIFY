"""Parsers for LANL Comprehensive Multi-Source Cyber-Security Events files.

The same parsers accept the real LANL files and the synthetic LANL-format-compatible
demo files, because both follow the published comma-separated schemas exactly.
"""
from __future__ import annotations

import gzip
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

# Exact LANL column orders.
SCHEMAS: dict[str, list[str]] = {
    "auth": ["time", "srcUser", "dstUser", "srcComputer", "dstComputer",
             "authType", "logonType", "authOrient", "outcome"],
    "proc": ["time", "user", "computer", "processName", "eventType"],
    "flow": ["time", "duration", "srcComputer", "srcPort", "dstComputer",
             "dstPort", "protocol", "packets", "bytes"],
    "dns": ["time", "srcComputer", "resolvedComputer"],
    "redteam": ["time", "user", "srcComputer", "dstComputer"],
}

# Map from LANL file stem to source type.
FILE_STEMS = {"auth": "auth", "proc": "proc", "flows": "flow", "flow": "flow",
              "dns": "dns", "redteam": "redteam"}

NULL_TOKENS = {"", "?"}
INTEGER_FIELDS = {"time", "duration", "packets", "bytes", "protocol"}


@dataclass
class ParsedRecord:
    source_type: str
    line_no: int
    raw_line: str
    fields: dict[str, object]


@dataclass
class ParseReport:
    source_type: str
    path: str
    total_lines: int = 0
    parsed: int = 0
    malformed: int = 0
    errors: list[str] = field(default_factory=list)  # first few error messages only

    def add_error(self, msg: str) -> None:
        self.malformed += 1
        if len(self.errors) < 10:
            self.errors.append(msg)


class MalformedRecord(ValueError):
    pass


def detect_source_type(path: Path) -> str | None:
    name = path.name.lower()
    for suffix in (".gz", ".txt", ".csv"):
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    for stem, source in FILE_STEMS.items():
        if name == stem or name.startswith(stem + "_") or name.startswith(stem + "-"):
            return source
    return None


def open_text(path: Path):
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace", newline="")
    return open(path, "rt", encoding="utf-8", errors="replace", newline="")


def clean_value(value: str) -> str | None:
    value = value.strip()
    return None if value in NULL_TOKENS else value


def parse_line(source_type: str, line: str, line_no: int) -> ParsedRecord:
    """Parse one CSV line. Raises MalformedRecord for structurally invalid rows."""
    columns = SCHEMAS[source_type]
    raw = line.rstrip("\r\n")
    parts = raw.split(",")
    if len(parts) != len(columns):
        raise MalformedRecord(f"line {line_no}: expected {len(columns)} fields, got {len(parts)}")
    fields: dict[str, object] = {}
    for name, value in zip(columns, parts):
        cleaned = clean_value(value)
        if cleaned is not None and name in INTEGER_FIELDS:
            try:
                fields[name] = int(cleaned)
            except ValueError:
                if name == "time":
                    raise MalformedRecord(f"line {line_no}: non-integer time {cleaned!r}") from None
                fields[name] = None  # tolerate bad numeric attributes, keep the event
        else:
            fields[name] = cleaned
    if fields["time"] is None:
        raise MalformedRecord(f"line {line_no}: missing time")
    if int(fields["time"]) < 0:  # type: ignore[arg-type]
        raise MalformedRecord(f"line {line_no}: negative time")
    return ParsedRecord(source_type, line_no, raw, fields)


def iter_records(path: Path, source_type: str, report: ParseReport) -> Iterator[ParsedRecord]:
    """Stream parsed records from a .txt/.txt.gz file, recording malformed rows in `report`."""
    with open_text(path) as handle:
        for line_no, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            report.total_lines += 1
            try:
                record = parse_line(source_type, line, line_no)
            except MalformedRecord as exc:
                report.add_error(str(exc))
                continue
            report.parsed += 1
            yield record
