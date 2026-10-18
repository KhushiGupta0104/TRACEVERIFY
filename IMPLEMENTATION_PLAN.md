# TRACEVERIFY — Implementation Plan

## 0. Findings from Phase 0 inspection

| Item | Finding |
|---|---|
| `PROJECT_REQUIREMENTS.md` | Not present in workspace → brief captured into `PROJECT_REQUIREMENTS.md`. |
| Synopsis (DOCX) | Mixed correlation approach (similarity + step-based) after Kotenko et al. 2022; PostgreSQL store; candidate timelines; no claim of causality. |
| Dataset ZIP | `auth` 244, `proc` 260, `dns` 192, `flows` 216 rows — **synthetic, LANL-format-compatible** (stated by bundled README). `redteam_seed_subset` 12 rows — stated by README to be the first 12 rows of the real LANL `redteam.txt.gz` (consistent with the published file; full file not present). Time range 100000–210694 s. |
| Data shape | Each seed has a tight chain (≈ −8 s … +31 s): matching logon → powershell/cmd/rundll32 on target → DNS from target → flows to resolved host, interleaved with `chrome.exe` / background distractors on other hosts. |
| Environment | Python 3.14.5 (`py`), Node 24.12 / npm 11.6, **no PostgreSQL installed**, no winget. C: has ~0 GB free → PostgreSQL 17.6 portable binaries installed to `D:\TraceVerifyPG`. |

### Discrepancies and resolution
* **Synopsis** mentions an optional "lightweight statistical/ML anomaly signal where feasible"; the **brief** forbids unnecessary ML.
  Resolution: the correlation score stays purely Entity–Temporal–Rule. A *frequency/rarity context* (how common a process or entity is in the store) is shown in event details as supporting context only, never in the score.
* **Synopsis** asks for performance measurement → each run records events-in-window, candidates evaluated, candidate reduction and latency.
* **Synopsis** mentions evaluation with red-team ground truth → red-team rows are used only as seeds and are **excluded from candidate evidence** (prevents label leakage). Full attack-chain ground truth does not exist, so no precision/recall is claimed.

## 1. Architecture

```
data/*.txt(.gz) ─► parsers ─► normalizer ─► ingest_service ─► PostgreSQL
                                                             │
React (Vite) ◄── FastAPI controllers ◄── investigation_service ◄── correlation_engine
                                                             ▲            │
                                                   repositories ◄─ scoring + rules
```

* `backend/app/rules` — event-type vocabulary + transition rules (pure Python, conditions on real fields).
* `backend/app/services/scoring.py` — Entity, Temporal, Rule, Final score (pure functions).
* `backend/app/services/correlation_engine.py` — bounded BFS expansion over a `CandidateProvider` interface (DB-backed in production, in-memory in unit tests).
* `backend/app/services/investigation_service.py` — persistence of runs/relationships, timeline + path construction.

## 2. Database
`events`, `entities`, `event_entities`, `investigations`, `relationships`, `correlation_rules`, `schema_migrations`.
Idempotent ingestion via a `dedup_key` unique constraint; JSONB `attributes` keeps source-specific fields.

## 3. Algorithm
1. Seed `s`, window `[t_s − before, t_s + after]`.
2. Frontier = {s}. For hop = 1..max_hops: retrieve events in window sharing ≥1 correlation entity (user/computer) with any frontier event, not already in the graph, not red-team, matching source filters.
3. Score each (frontier parent p, candidate c): `E` (shared users/computers + host continuity), `T` (exp decay of |Δt| with ordering factor), `R` (matching transition rule, full/partial condition).
   `Final = wE·E + wT·T + wR·R`.
4. For each candidate keep the best parent; accept if `Final ≥ threshold`. Rejected candidates keep their best edge with status `rejected` for transparency.
5. Node budget (`max_nodes`) keeps the graph bounded.
6. Step-based path reconstruction: each accepted event's primary parent = best-scoring *earlier* accepted event (seed first), cycle-checked; ≤1 supporting edge per event. Inclusion is decided only by step 4, so lowering the threshold never removes events (absent budget truncation).
7. Timeline = seed + accepted events ordered by time; paths = primary-parent chains from each leaf back to the seed.

*Change during implementation:* the first version attached every hop-1 event directly to the seed, hiding the process → DNS → flow chain; step 6 was added to recover it (verified by `test_step_chain_parentage`).

## 4. Testing
Unit: parsers, missing values, normalisation, each score, weights validation, rules, engine (thresholds, window, cycles, hops).
Integration (PostgreSQL `traceverify_test`): ingestion, duplicate prevention, all APIs, reruns, monotonic threshold, window narrowing, DB provenance.
Frontend: production build + Playwright (system Edge) end-to-end smoke test.

## 5. Acceptance criteria
See README §"Verification status" — every claim there is backed by an executed command.
