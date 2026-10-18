TRACEVERIFY — Synthetic LANL-Format Demonstration Dataset
==========================================================

Purpose
-------
This is a SMALL synthetic dataset created for the TRACEVERIFY third-year
college cybersecurity project. It is designed to exercise the project's
Entity + Temporal + Rule correlation engine without requiring the full
LANL dataset.

IMPORTANT: These synthetic rows are NOT LANL observations. They are
LANL-FORMAT-COMPATIBLE demonstration data.

Source grounding
----------------
The schemas follow the published LANL Cyber1 dataset structure and the
documented examples in the G-Research dgraph-lanl-csr preprocessing project.

The uploaded real redteam.txt.gz was inspected. The first 12 real
red-team seed rows were used only as investigation-seed entities/timestamps.
The other four files are synthetic and intentionally constructed around
those seeds.

Files
-----
auth.txt.gz
  time,srcUser,dstUser,srcComputer,dstComputer,authType,logonType,authOrient,outcome

proc.txt.gz
  time,user,computer,processName,eventType

flows.txt.gz
  time,duration,srcComputer,srcPort,dstComputer,dstPort,protocol,packets,bytes

dns.txt.gz
  time,srcComputer,resolvedComputer

redteam_seed_subset.txt.gz
  time,user,srcComputer,dstComputer

Design
------
Each selected seed has a coherent cross-source chain:
  red-team seed
      -> authentication
      -> process activity
      -> DNS resolution
      -> network flow

The dataset also contains:
- normal/background events
- related suspicious-looking events
- unrelated events
- temporal distractors
- shared users/computers for entity correlation
- compatible transitions for rule scoring
- enough variation to test thresholds and ranking

The DNS file follows the LANL schema: resolvedComputer is a computer
identifier (Cxxxx), not a human-readable domain name.

The flow protocol values use common numeric protocol identifiers such as
6 (TCP) and 17 (UDP), consistent with the documented dataset examples.

Recommended TRACEVERIFY use
---------------------------
1. Load these files into the ingestion/preprocessing pipeline.
2. Treat redteam_seed_subset as investigation seeds, not detections.
3. Select a seed.
4. Retrieve candidate events by shared entities + temporal window.
5. Score candidates using:
      Entity Score
      Temporal Score
      Rule Compatibility Score
6. Apply the configurable threshold.
7. Build the evidence relationships/path and candidate incident timeline.
8. Display reasons for each relationship.

This dataset is intentionally small. It should be used for development and
demonstration. The same parser/database/correlation architecture should later
accept a selected real LANL window.

Reference
---------
LANL Cyber1 dataset schema and examples were cross-checked against:
G-Research/dgraph-lanl-csr, SPARK.md
https://github.com/G-Research/dgraph-lanl-csr/blob/master/SPARK.md
