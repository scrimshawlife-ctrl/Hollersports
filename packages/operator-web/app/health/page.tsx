"use client";

import { useCallback, useEffect, useState } from "react";
import { AuthorityChip, toneForStatus } from "@/components/AuthorityChip";
import { DataTable, type Column } from "@/components/DataTable";
import {
  ApiError,
  fieldOrDash,
  getDashboard,
  getHealth,
  getPortfolio,
  getPromotion,
  type Json,
} from "@/lib/api";

type SourceRow = {
  key: string;
  id: string;
  type: string;
  enabled: string;
};

function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" ? (v as Record<string, unknown>) : {};
}

function asList(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

export default function HealthPage() {
  const [health, setHealth] = useState<Json | null>(null);
  const [dashboard, setDashboard] = useState<Json | null>(null);
  const [portfolio, setPortfolio] = useState<Json | null>(null);
  const [promotion, setPromotion] = useState<Json | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const [h, d, p, promo] = await Promise.all([
        getHealth(),
        getDashboard(),
        getPortfolio(),
        getPromotion(),
      ]);
      setHealth(h);
      setDashboard(d);
      setPortfolio(p);
      setPromotion(promo);
    } catch (e) {
      const msg =
        e instanceof ApiError
          ? e.message
          : e instanceof Error
            ? e.message
            : "health load failed";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const panels = asRecord(dashboard?.panels);
  const sourcesPanel = asRecord(panels.sources);
  const sourceHealth = asRecord(sourcesPanel.source_health);
  const performance = asRecord(
    portfolio?.performance ?? panels.performance_metrics,
  );
  const promo = asRecord(promotion);
  const registrySources = asList(health?.sources).filter(
    (s): s is Record<string, unknown> => !!s && typeof s === "object",
  );

  const sourceRows: SourceRow[] = registrySources.map((s, i) => ({
    key: String(s.id ?? i),
    id: String(s.id ?? "—"),
    type: String(s.type ?? "—"),
    enabled: String(s.enabled ?? "—"),
  }));

  const sourceColumns: Column<SourceRow>[] = [
    {
      key: "id",
      header: "Source",
      render: (r) => <span className="mono">{r.id}</span>,
    },
    {
      key: "type",
      header: "Type",
      render: (r) => <span className="mono">{r.type}</span>,
    },
    {
      key: "enabled",
      header: "Enabled",
      render: (r) => r.enabled,
    },
  ];

  const perfKeys = [
    "status",
    "sample_size",
    "roi",
    "hit_rate",
    "clv_retention",
    "max_drawdown",
    "volatility",
    "sharpe_like_ratio",
    "profit_factor",
    "average_stake",
    "reason",
  ] as const;

  const passedGates = asList(promo.passed_gates).map(String);
  const failedGates = asList(promo.failed_gates).map(String);

  const runLog: { key: string; label: string; value: string }[] = [
    {
      key: "run_id",
      label: "run_id",
      value: fieldOrDash(dashboard?.run_id).text,
    },
    {
      key: "dashboard_status",
      label: "dashboard.status",
      value: fieldOrDash(dashboard?.status).text,
    },
    {
      key: "dashboard_authority",
      label: "dashboard.authority",
      value: fieldOrDash(dashboard?.authority).text,
    },
    {
      key: "portfolio_status",
      label: "portfolio.status",
      value: fieldOrDash(portfolio?.status, "empty portfolio").text,
    },
    {
      key: "portfolio_run",
      label: "portfolio.run_id",
      value: fieldOrDash(portfolio?.run_id).text,
    },
    {
      key: "health_status",
      label: "api.health",
      value: fieldOrDash(health?.status).text,
    },
    {
      key: "mode",
      label: "mode",
      value: fieldOrDash(health?.mode, "not reported").text,
    },
    {
      key: "capital",
      label: "capital_authority",
      value: fieldOrDash(health?.capital_authority).text,
    },
  ];

  return (
    <>
      <header className="page-header">
        <h1>Health</h1>
        <div className="actions-row">
          <AuthorityChip
            label={String(health?.status ?? (loading ? "…" : "—"))}
            tone={toneForStatus(health?.status)}
          />
          <button
            type="button"
            className="btn"
            disabled={loading}
            onClick={() => void load()}
          >
            {loading ? "Loading…" : "Refresh"}
          </button>
        </div>
      </header>

      {error && (
        <p className="error-line" role="alert">
          {error}
        </p>
      )}

      <section className="section" aria-label="Sources">
        <h2 className="section-title">Sources</h2>
        <div className="actions-row" style={{ marginBottom: 12 }}>
          <AuthorityChip
            label={String(
              sourceHealth.status ?? sourcesPanel.status ?? "—",
            )}
            tone={toneForStatus(
              sourceHealth.status ?? sourcesPanel.status,
            )}
            title={
              sourceHealth.reason != null
                ? String(sourceHealth.reason)
                : undefined
            }
          />
          <span className="muted mono" style={{ fontSize: 12 }}>
            source_id={String(sourcesPanel.source_id ?? "—")}
          </span>
        </div>
        <DataTable
          columns={sourceColumns}
          rows={sourceRows}
          rowKey={(r) => r.key}
          emptyMessage="No sources in registry summary"
        />
        {asList(sourceHealth.missing_required_fields).length > 0 && (
          <p className="status-line">
            missing_required_fields:{" "}
            {asList(sourceHealth.missing_required_fields)
              .map(String)
              .join(", ")}
          </p>
        )}
      </section>

      <section className="section" aria-label="Performance">
        <h2 className="section-title">Performance</h2>
        <div className="actions-row" style={{ marginBottom: 12 }}>
          <AuthorityChip
            label={String(performance.status ?? "—")}
            tone={toneForStatus(performance.status)}
            title={
              performance.reason != null
                ? String(performance.reason)
                : undefined
            }
          />
        </div>
        <dl className="kv-list">
          {perfKeys.map((k) => {
            const f = fieldOrDash(performance[k], `missing ${k}`);
            return (
              <div key={k} style={{ display: "contents" }}>
                <dt>{k}</dt>
                <dd className="tabular" title={f.reason}>
                  {f.text}
                  {f.reason && f.text === "—" ? (
                    <span className="muted"> · {f.reason}</span>
                  ) : null}
                </dd>
              </div>
            );
          })}
        </dl>
      </section>

      <section className="section" aria-label="Promotion">
        <h2 className="section-title">Promotion</h2>
        <div className="actions-row" style={{ marginBottom: 12 }}>
          <AuthorityChip
            label={String(promo.status ?? "—")}
            tone={toneForStatus(promo.status)}
            title={promo.reason != null ? String(promo.reason) : undefined}
          />
          <span className="muted mono" style={{ fontSize: 12 }}>
            target={String(promo.target_id ?? "—")} /{" "}
            {String(promo.target_type ?? "—")}
          </span>
        </div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 16,
          }}
        >
          <div>
            <h3 className="section-title">Passed gates</h3>
            <ul className="gate-list">
              {passedGates.length === 0 ? (
                <li className="muted">— none</li>
              ) : (
                passedGates.map((g) => (
                  <li key={g}>
                    <AuthorityChip label={g} tone="neutral" />
                  </li>
                ))
              )}
            </ul>
          </div>
          <div>
            <h3 className="section-title">Failed gates</h3>
            <ul className="gate-list">
              {failedGates.length === 0 ? (
                <li className="muted">— none</li>
              ) : (
                failedGates.map((g) => (
                  <li key={g}>
                    <AuthorityChip label={g} tone="fail" />
                  </li>
                ))
              )}
            </ul>
          </div>
        </div>
      </section>

      <section className="section" aria-label="Run log">
        <h2 className="section-title">Run log</h2>
        <dl className="kv-list">
          {runLog.map((row) => (
            <div key={row.key} style={{ display: "contents" }}>
              <dt>{row.label}</dt>
              <dd>{row.value}</dd>
            </div>
          ))}
        </dl>
      </section>
    </>
  );
}
