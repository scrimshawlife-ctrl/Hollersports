# HollerSports Operator Web (Cobalt Workbench)

Paper-only operator shell: **Today · Book · Health**.

Hallmark: Workbench · atmospheric · Cobalt · N3 · Ft4.

## Prerequisites

- Node 20+
- Operator API on `http://127.0.0.1:8000` (`hollersports.api.app:create_app`)

## Setup

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Next rewrites `/v1/*` → `:8000`.

## Build

```bash
npm run build
npm start
```

## Fixture day flow

1. Start API: `uvicorn hollersports.api.app:create_app --factory --port 8000`
2. Today → **Ingest day001** → **Compete** → **Paper** → **Settle**
3. Book → candidates + paper portfolio
4. Health → sources / performance / promotion / run log

## Guardrails

- Mode is locked **PAPER_ONLY** (colophon). No live capital path.
- No live-wagering UX labels or live-approved mode strings in source (CI greps the operator-web tree).
