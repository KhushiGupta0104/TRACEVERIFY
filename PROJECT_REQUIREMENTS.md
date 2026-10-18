# TRACEVERIFY — Project Requirements (captured from the project brief)

> No `PROJECT_REQUIREMENTS.md` existed in the workspace when implementation began,
> so this file records the brief given to the implementer. The academic synopsis
> (`../TRACEVERIFY_FINAL_DETECTION_CORRELATION_INVESTIGATION (1).docx`) remains the
> authoritative statement of scope and methodology.

## 1. Core purpose
Correlate heterogeneous cybersecurity events and reconstruct an EXPLAINABLE candidate
incident timeline from a selected investigation seed.

    LANL/synthetic evidence → Parse → Normalize → PostgreSQL → Select investigation seed
    → Retrieve candidate events → Entity + Temporal + Rule correlation → Score/rank
    → Threshold → Evidence relationships/paths → Incident timeline + evidence graph → Explanation

The system must never claim correlation proves attacker intent or causality.

## 2. Dataset
* Red-team seed rows (real LANL `redteam.txt.gz` rows) are investigation SEEDS, not detections.
* `auth`, `proc`, `dns`, `flows` are a small SYNTHETIC / LANL-FORMAT-COMPATIBLE dataset and must be labelled as such.
* Exact LANL schemas:
  * AUTH: `time,srcUser,dstUser,srcComputer,dstComputer,authType,logonType,authOrient,outcome`
  * PROC: `time,user,computer,processName,eventType`
  * FLOWS: `time,duration,srcComputer,srcPort,dstComputer,dstPort,protocol,packets,bytes`
  * DNS: `time,srcComputer,resolvedComputer`
  * REDTEAM: `time,user,srcComputer,dstComputer`
* Must later accept selected real LANL windows without redesign. Never ingest the full 1.6B-event dataset.

## 3. Correlation engine
No Isolation Forest / GNN / deep learning / unnecessary ML.

    FinalScore = w1·EntityScore + w2·TemporalScore + w3·RuleScore

Weights and threshold configurable; component scores in [0,1]; weights non-negative and sum to 1.
Every relationship stores entity/temporal/rule/final score, time difference, shared entities,
matched rule and a human-readable explanation. Rank by FinalScore; apply threshold.

## 4. Database — PostgreSQL
Tables: `events`, `entities`, `event_entities`, `investigations`, `relationships`, `correlation_rules`.
Common fields + source-specific attributes; indexes on timestamps and entity lookups.

## 5. Backend — Python, FastAPI, SQLAlchemy
`backend/app/{models,schemas,controllers,services,repositories,rules,database}`

    GET  /api/investigations/seeds
    POST /api/investigations/start
    GET  /api/investigations/{id}
    GET  /api/investigations/{id}/events
    GET  /api/investigations/{id}/relationships
    GET  /api/events/{event_id}
    POST /api/investigations/{id}/rerun

## 6. Frontend — React
A. Investigation view: seed selection, temporal window, threshold, source filters, run; show seed,
   parameters, candidate count, relationship count, highest-scoring evidence.
B. Incident view: incident timeline, interactive evidence graph, evidence details (scores, shared
   entities, time difference, matched rule, explanation). It must be obvious WHY an event was included.

## 7. Visual design
Serious forensic-workstation look: near-black/charcoal/deep navy, muted cyan, desaturated violet,
subtle amber, off-white text, IBM Plex Sans / Inter + JetBrains Mono. Thin borders, compact panels.
No white SaaS dashboard, neon, glow, glassmorphism, purple gradients, hacker imagery or gratuitous animation.

## 8–13. Structure, processing, demo, setup, scope
See README.md. Out of scope: RabbitMQ, Docker/Kubernetes, Zeek, Isolation Forest, GNN, transformers,
SHA-256/Ed25519 security layers, NestJS, authentication systems, microservices, unnecessary ML.
