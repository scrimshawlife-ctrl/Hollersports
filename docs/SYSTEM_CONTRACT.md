# HollerSports System Contract v0.2

## Authority

HollerSports is a **standalone sports market intelligence operator**.  
Default mode: **PAPER_ONLY** / **CANON-SHADOW**.

## Non-negotiable laws

1. HollerSports must **never execute live capital autonomously**.
2. All market data must pass **source health** before strategies consume it.
3. Strategies may **emit candidates only**; they cannot execute or promote.
4. Execution must pass **execution_guard** before paper portfolio entry.
5. Dashboard and operator projections are **PROJECTION_ONLY**.
6. Promotion evaluation may **recommend review only**; it cannot authorize live execution.
7. Settlement requires **outcome provenance** before promotion eligibility.
8. Same inputs must produce **identical outputs** across 12 deterministic runs (when golden suite is active).
9. Missing provenance, odds, or lines must **fail closed** (`NOT_COMPUTABLE` / `REJECTED`) — never invent certainty.
10. Live transition requires **explicit human approval outside** this system (not a v1 product feature).

## Packet flags (v1)

| Flag | Value |
|------|--------|
| `capital_authority` | always `false` |
| `execution_authority` | always `false` |
| Execution `mode` | `PAPER_ONLY` only |

## Violation

Any violation is **SYSTEM_FAILURE** and blocks promotion review.

## Related

- [Repository Atlas](atlas/HOLLERSPORTS_ATLAS.md)
- [Abraxas lineage (concept-only)](ABRAXAS_LINEAGE.md)
- [Design spec](superpowers/specs/2026-08-04-hollersports-standalone-design.md)
