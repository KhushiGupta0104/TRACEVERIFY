"""Ingest LANL-format evidence files into PostgreSQL.

Usage (from backend/):
    # demo dataset (synthetic evidence + real red-team seed subset)
    python -m scripts.ingest --evidence-dir ../data/synthetic --redteam ../data/raw/redteam_seed_subset.txt.gz

    # a selected real LANL window (labelled as real LANL data), keeping rows within
    # ±3600 s of any red-team seed
    python -m scripts.ingest --evidence-dir ../data/raw/lanl_window --label lanl \
        --redteam ../data/raw/redteam.txt.gz --around-redteam 3600

Files are recognised by name: auth*, proc*, dns*, flows*, redteam* (.txt or .txt.gz).
Re-running is safe: duplicate rows are skipped.
"""
import argparse
import sys
from pathlib import Path

from app.database.session import engine
from app.services.ingestion.ingest_service import (
    LANL_LABEL, REDTEAM_LABEL, SYNTHETIC_LABEL, TimeFilter, dataset_counts, ingest_file, read_seed_times,
)
from app.services.ingestion.parsers import detect_source_type

LABELS = {"synthetic": SYNTHETIC_LABEL, "lanl": LANL_LABEL}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--evidence-dir", type=Path, help="directory with auth/proc/dns/flows files")
    parser.add_argument("--redteam", type=Path, help="red-team seed file (redteam.txt[.gz])")
    parser.add_argument("--label", choices=LABELS, default="synthetic",
                        help="provenance label for evidence files (default: synthetic)")
    parser.add_argument("--t-min", type=int, help="keep evidence rows with time >= T_MIN")
    parser.add_argument("--t-max", type=int, help="keep evidence rows with time <= T_MAX")
    parser.add_argument("--around-redteam", type=int, metavar="SECONDS",
                        help="keep evidence rows within ±SECONDS of any red-team seed")
    args = parser.parse_args()
    if not args.evidence_dir and not args.redteam:
        parser.error("give --evidence-dir and/or --redteam")

    seed_times = read_seed_times(args.redteam) if args.redteam else []
    tf = TimeFilter(args.t_min, args.t_max, seed_times, args.around_redteam)

    jobs: list[tuple[Path, str, TimeFilter | None]] = []
    if args.redteam:
        jobs.append((args.redteam, REDTEAM_LABEL, None))
    if args.evidence_dir:
        files = sorted(p for p in args.evidence_dir.iterdir()
                       if p.is_file() and detect_source_type(p) not in (None, "redteam"))
        if not files:
            print(f"No LANL-format evidence files found in {args.evidence_dir}", file=sys.stderr)
            return 1
        jobs += [(p, LABELS[args.label], tf) for p in files]

    for path, label, filt in jobs:
        res = ingest_file(engine, path, label, filt)
        r = res.report
        print(f"{path.name:<28} {res.source_type:<8} lines={r.total_lines:<6} parsed={r.parsed:<6} "
              f"malformed={r.malformed:<4} filtered={res.filtered_out:<5} inserted={res.inserted:<6} "
              f"duplicates={res.duplicates}")
        for err in r.errors:
            print(f"    ! {err}")

    print("\nEvidence store contents:")
    for row in dataset_counts(engine):
        print(f"  {row['source_type']:<8} {row['count']:>6}  t=[{row['min_ts']}, {row['max_ts']}]  {row['dataset_label']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
