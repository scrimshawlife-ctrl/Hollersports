"use client";

import { useCallback, useEffect, useState } from "react";
import { AuthorityChip, toneForStatus } from "@/components/AuthorityChip";
import {
  ApiError,
  cacheCompetition,
  fieldOrDash,
  getDashboard,
  postCompete,
  postFreeFirst,
  postFullDay,
  postIngest,
  postPaper,
  postSettle,
  type Json,
} from "@/lib/api";

type ActionId =
  | "ingest"
  | "compete"
  | "paper"
  | "settle"
  | "refresh"
  | "fullday"
  | "freefirst";

function panelField(
  dashboard: Json | null,
  path: string[],
): { text: string; reason?: string } {
  if (!dashboard) {
    return { text: "—", reason: "dashboard not loaded" };
  }
  let cur: unknown = dashboard;
  for (const key of path) {
    if (cur === null || cur === undefined || typeof cur !== "object") {
      return { text: "—", reason: `missing ${path.join(".")}` };
    }
    cur = (cur as Record<string, unknown>)[key];
  }
  return fieldOrDash(cur, `missing ${path.join(".")}`);
}

const FIXTURES = ["day001", "day002"] as const;
type FixtureId = (typeof FIXTURES)[number];

export default function TodayPage() {
  const [dashboard, setDashboard] = useState<Json | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<ActionId | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastAction, setLastAction] = useState<string | null>(null);
  const [fixture, setFixture] = useState<FixtureId>("day001");
  const [allowModelEdge, setAllowModelEdge] = useState(false);

  const refresh = useCallback(async () => {
    setError(null);
    try {
      const d = await getDashboard();
      setDashboard(d);
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? e.message
          : e instanceof Error
            ? e.message
            : "dashboard fetch failed";
      setError(msg);
      setDashboard(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function runAction(id: ActionId, fn: () => Promise<Json>) {
    setBusy(id);
    setError(null);
    setLastAction(null);
    try {
      const result = await fn();
      if (id === "compete") {
        cacheCompetition(result);
      }
      setLastAction(`${id} → ${String(result.status ?? "ok")}`);
      await refresh();
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? e.message
          : e instanceof Error
            ? e.message
            : `${id} failed`;
      setError(msg);
    } finally {
      setBusy(null);
    }
  }

  const runId = panelField(dashboard, ["run_id"]);
  const status = panelField(dashboard, ["status"]);
  const authority = panelField(dashboard, ["authority"]);
  const capital = panelField(dashboard, ["capital_authority"]);
  const portfolioId = panelField(dashboard, ["portfolio_id"]);
  const approved = panelField(dashboard, [
    "panels",
    "paper_portfolio_summary",
    "approved_count",
  ]);
  const rejected = panelField(dashboard, [
    "panels",
    "paper_portfolio_summary",
    "rejected_count",
  ]);
  const settlementPending = panelField(dashboard, [
    "panels",
    "settlement_queue",
    "pending",
  ]);
  const promoStatus = panelField(dashboard, [
    "panels",
    "promotion_gate_status",
    "status",
  ]);
  const sourceStatus = panelField(dashboard, ["panels", "sources", "status"]);

  const disabled = busy !== null || loading;

  return (
    <>
      <header className="page-header">
        <h1>Today</h1>
        <AuthorityChip
          label={String(dashboard?.authority ?? "PROJECTION_ONLY")}
          tone={toneForStatus(dashboard?.authority)}
        />
      </header>

      <section className="section" aria-label="Overview">
        <h2 className="section-title">Overview</h2>
        <dl className="overview-strip">
          <OverviewField label="run_id" value={runId} />
          <OverviewField label="status" value={status} />
          <OverviewField label="authority" value={authority} />
          <OverviewField label="capital_authority" value={capital} />
          <OverviewField label="portfolio_id" value={portfolioId} />
          <OverviewField label="paper approved" value={approved} />
          <OverviewField label="paper rejected" value={rejected} />
          <OverviewField label="settlement pending" value={settlementPending} />
          <OverviewField label="promotion" value={promoStatus} />
          <OverviewField label="ingest status" value={sourceStatus} />
        </dl>
      </section>

      <section className="section" aria-label="Actions">
        <h2 className="section-title">Actions</h2>
        <div className="actions-row" style={{ marginBottom: 12, gap: 16 }}>
          <label className="muted" style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
            Fixture
            <select
              className="mono"
              value={fixture}
              disabled={disabled}
              aria-label="Fixture day"
              onChange={(e) => setFixture(e.target.value as FixtureId)}
            >
              {FIXTURES.map((id) => (
                <option key={id} value={id}>
                  {id}
                </option>
              ))}
            </select>
          </label>
          <label
            className="muted"
            style={{ display: "inline-flex", alignItems: "center", gap: 8 }}
            title="Requests forecast weighting; model edge unlocks only when evidence calibration is RELIABLE (see Health → Calibration). Markets need model_probability (day002). Still SHADOW_ONLY — no money."
          >
            <input
              type="checkbox"
              checked={allowModelEdge}
              disabled={disabled}
              onChange={(e) => setAllowModelEdge(e.target.checked)}
            />
            Allow model edge (evidence calibration)
          </label>
        </div>
        <div className="actions-row">
          <button
            type="button"
            className="btn btn-primary"
            disabled={disabled}
            onClick={() => void runAction("fullday", () => postFullDay(fixture))}
          >
            {busy === "fullday" ? "Running day…" : `Run full ${fixture}`}
          </button>
          <button
            type="button"
            className="btn"
            disabled={disabled}
            title="Optional network observation (ESPN; Odds API if key set). No money."
            onClick={() =>
              void runAction("freefirst", () =>
                postFreeFirst({ espn_only: false, auto_compete: true }),
              )
            }
          >
            {busy === "freefirst" ? "Observing…" : "Free-first live observe"}
          </button>
          <button
            type="button"
            className="btn"
            disabled={disabled}
            onClick={() => void runAction("ingest", () => postIngest(fixture))}
          >
            {busy === "ingest" ? "Ingesting…" : `Ingest ${fixture}`}
          </button>
          <button
            type="button"
            className="btn"
            disabled={disabled}
            onClick={() =>
              void runAction("compete", () =>
                postCompete({ allow_forecast_weighting: allowModelEdge }),
              )
            }
          >
            {busy === "compete" ? "Competing…" : "Compete"}
          </button>
          <button
            type="button"
            className="btn"
            disabled={disabled}
            onClick={() => void runAction("paper", () => postPaper())}
          >
            {busy === "paper" ? "Papering…" : "Paper top-N"}
          </button>
          <button
            type="button"
            className="btn"
            disabled={disabled}
            onClick={() => void runAction("settle", () => postSettle())}
          >
            {busy === "settle" ? "Settling…" : "Settle"}
          </button>
          <button
            type="button"
            className="btn"
            disabled={disabled}
            onClick={() =>
              void runAction("refresh", async () => {
                await refresh();
                return { status: "REFRESHED" };
              })
            }
          >
            {busy === "refresh" || loading ? "Refreshing…" : "Refresh"}
          </button>
        </div>
        {error && (
          <p className="error-line" role="alert">
            {error}
          </p>
        )}
        {lastAction && !error && (
          <p className="status-line" aria-live="polite">
            {lastAction}
          </p>
        )}
      </section>
    </>
  );
}

function OverviewField({
  label,
  value,
}: {
  label: string;
  value: { text: string; reason?: string };
}) {
  return (
    <div className="overview-field">
      <dt>{label}</dt>
      <dd title={value.reason}>
        {value.text}
        {value.reason && value.text === "—" && (
          <span className="muted"> · {value.reason}</span>
        )}
      </dd>
    </div>
  );
}
