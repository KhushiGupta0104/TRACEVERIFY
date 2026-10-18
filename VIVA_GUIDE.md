# TRACEVERIFY — Viva Guide

A short explanation of what we built and why, in plain language.

## 1. The problem in one paragraph
During an incident, the evidence is scattered: a logon in the authentication logs, a process on
an endpoint, a DNS lookup, a network flow. Each log has a different format, and no single record
tells the whole story. *Event correlation* finds which records plausibly belong together.
TRACEVERIFY takes one known suspicious event (a **seed**), finds related evidence across the four
sources, scores each link, and draws a **candidate incident timeline and evidence graph**. Every
link comes with a written reason.

## 2. Why "candidate" and not "attack chain"?
Correlation shows that two events are *related* (same user, same host, close in time,
sensible order). It cannot prove that one *caused* the other, or that an attacker intended it.
So we call results *candidate evidence relationships*, and the UI says so on every incident view.

## 3. Data
* The **LANL Comprehensive Multi-Source Cyber-Security Events** dataset (58 days, auth/proc/dns/flows
  plus red-team labels) is our reference format. The full dataset has about 1.6 billion events,
  far too many for a lab project.
* We use **12 real red-team rows as seeds**, plus a small **synthetic, LANL-format-compatible**
  evidence set built around them. Synthetic rows are labelled as synthetic everywhere.
* Red-team rows are **starting points, not detections**. We also exclude them from candidate
  evidence, so the labels never influence the scores.

## 4. Modules (and where they live)
| Module | Folder / file | One-line job |
|---|---|---|
| Parsing | `services/ingestion/parsers.py` | Read `.txt/.gz`, split by the exact LANL schema, turn `?` into null, reject malformed rows |
| Normalization | `services/ingestion/normalizer.py` | Map every source to common fields (time, type, user, src/dst host) + keep source-specific fields in JSON; extract entities |
| Storage | `database/schema.sql`, `ingest_service.py` | Batched, idempotent insert into PostgreSQL with indexes |
| Rules | `rules/definitions.py` | 12 transition rules such as Logon → Process, Process → DNS, DNS → Flow |
| Scoring | `services/scoring.py` | Entity, Temporal, Rule and Final scores |
| Engine | `services/correlation_engine.py` | Retrieve → score → threshold → expand → reconstruct paths |
| Service + API | `services/investigation_service.py`, `controllers/` | Persist runs, build timeline/paths, REST endpoints |
| UI | `frontend/src` | Seed selection, parameters, timeline, graph, explanation panel |

## 5. The algorithm, step by step
1. Pick a seed and a time window (for example 5 min before to 30 min after).
2. **Retrieve candidates** with SQL: events in the window that share a user or computer with the
   current evidence. Indexes on time and entity make this fast.
3. **Score** each candidate against the event that found it:
   * **EntityScore**: shared user +0.45, each shared computer +0.30 (max two), *host continuity*
     +0.25. Host continuity means the new event starts on the machine the previous event landed on.
   * **TemporalScore** = e^(−|Δt|/τ): 1.0 at the same second, about 0.37 after τ seconds.
     Events that come *before* their parent are multiplied by 0.85.
   * **RuleScore**: does the transition make sense, checked on real fields? Example: R03 says a
     DNS lookup after a process scores 1.0 only if the lookup comes from the *same host*.
4. **FinalScore** = w₁·E + w₂·T + w₃·R. The weights default to 0.4/0.3/0.3 and must sum to 1.
5. **Threshold**: keep links with Final ≥ threshold; store the rest as *rejected*, with reasons.
6. **Expand**: accepted events become the new frontier (bounded by rounds and a maximum event count).
7. **Reconstruct paths**: each accepted event links to its best-scoring *earlier* event. That
   turns a star around the seed into a real chain: seed → cmd.exe → DNS → flow.
8. **Timeline** = all accepted events sorted by time. **Paths** = chains from each leaf back to the seed.

## 6. Worked example (seed 01, threshold 0.60)
DNS lookup `C1003 → C901`, 4 s after `cmd.exe` on C1003:
* Entity = 0.30 (shared C1003) + 0.25 (continuity on C1003) = **0.55**
* Temporal = e^(−4/300) = **0.99**
* Rule = R03, full match = **1.00**
* Final = 0.4·0.55 + 0.3·0.99 + 0.3·1.00 = **0.816** ≥ 0.60 → accepted, hop 2.

A rejected example: `powershell.exe` on C728, 10 minutes later, shares only the user: E 0.45,
T 0.12, R 0 → **0.217** → rejected.

## 7. Why these design decisions?
* **No ML / GNN**: the synopsis requires an explainable mixed method (Kotenko et al. 2022).
  Every number on screen can be recomputed by hand.
* **PostgreSQL**: relational joins over entities and time, JSONB for source-specific fields,
  indexes for window queries, and constraints (scores in [0,1], no self-loops, unique edges).
* **Rules ignore time; the temporal score ignores rules.** This keeps each dimension
  independent, and proximity alone cannot get an event accepted.
* **Deduplication key**: re-running ingestion is safe, yet legitimately repeated LANL lines are kept.
* **Bounded expansion and acyclic edges**: the graph cannot explode or loop.
* **Rejected candidates are stored too**: an analyst can see *why* something was left out.

## 8. Testing (what we can claim)
Unit tests for parsers, scores, rules and the engine. Integration tests against a real PostgreSQL
test database for every API. A live audit script that checks every displayed event against the
database row and the original file line. A Playwright end-to-end test that clicks through the UI
in Edge. We verified that lowering the threshold never removes evidence and that a narrower
window never returns events outside it.

## 9. Likely viva questions
* *Is this detection?* No. It is investigation support that starts from a known seed.
* *Why is the default threshold 0.60?* Under 0.4/0.3/0.3 weights, an event that shares one host
  and happens at the same second but matches no rule scores 0.52, so it is rejected. Coherent
  chain links score 0.7–1.0.
* *What does a hop mean?* Hop 1 is directly linked to the seed. Hop n is linked through n−1
  intermediate events.
* *What would change with real LANL data?* Nothing in the code. Ingest a window with `--label lanl
  --around-redteam`. Hub hosts would argue for IDF-style entity weighting (future work).
* *Limitations?* Synthetic evidence, hand-set weights, no full ground truth for whole chains.
