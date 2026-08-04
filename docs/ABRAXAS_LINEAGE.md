# Abraxas lineage (concept-only)

HollerSports **does not require Abraxas** to install, test, or run.

Useful Abraxas **ideas** are reimplemented locally. This document maps lineage so future optional export adapters stay honest.

| Abraxas idea | HollerSports form | Path |
|--------------|-------------------|------|
| Authority lanes | Packet `authority` enums + locks | `hollersports/governance/authority.py` |
| Fail-closed | `NOT_COMPUTABLE` / `REJECTED` builders | `hollersports/governance/fail_closed.py` |
| Calibration gate | Model edge gated off until reliable | `hollersports/governance/gates.py` |
| Runes as pure ops | Named modules under `runes/` | `hollersports/runes/` |
| Packet contracts | JSON Schema + Pydantic | `schemas/json/`, `hollersports/schemas/` |
| Source health | Pre-strategy gate | `hollersports/runes/source_health.py` |
| Dual-lane | Market strategies free; model edge gated | `hollersports/strategies/` |
| Promotion | Review statuses only (when implemented) | design §8; pipeline TBD |
| Projection-only UI | Dashboard must not mutate authority | design §6; API/UI TBD |

## Dependency direction

```text
HollerSports (standalone)  ──optional export──►  Abraxas-shaped shadow packets
Abraxas (optional consumer) ──imports──►  those packets if present
```

Never: HollerSports imports Abraxas as a runtime dependency.

## Not imported

- ABX-Runes / YGGDRASIL engines  
- AAL-Viz runtime  
- Canon Spine service  
- Symbolic/ritual ticket weighting  

See [SYSTEM_CONTRACT.md](SYSTEM_CONTRACT.md) and [HOLLERSPORTS_ATLAS.md](atlas/HOLLERSPORTS_ATLAS.md).
