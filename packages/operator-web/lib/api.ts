/**
 * Browser client for HollerSports operator API.
 * All paths are same-origin `/v1/*` and rewritten to :8000 by next.config.
 */

export type Json = Record<string, unknown>;

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

async function parseBody(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

async function request<T = Json>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
    cache: "no-store",
  });
  const body = await parseBody(res);
  if (!res.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : res.statusText;
    throw new ApiError(detail || `HTTP ${res.status}`, res.status, body);
  }
  return body as T;
}

export function getDashboard() {
  return request<Json>("/v1/dashboard");
}

export function getPortfolio() {
  return request<Json>("/v1/portfolio");
}

export function getPromotion() {
  return request<Json>("/v1/promotion");
}

export function getReliability() {
  return request<Json>("/v1/reliability");
}

export function getHealth() {
  return request<Json>("/v1/health");
}

export function postIngest(fixture = "day001") {
  return request<Json>("/v1/runs/ingest", {
    method: "POST",
    body: JSON.stringify({ fixture }),
  });
}

export function postCompete() {
  return request<Json>("/v1/runs/compete", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function postPaper(portfolioId = "default", candidateIds?: string[]) {
  return request<Json>("/v1/runs/paper", {
    method: "POST",
    body: JSON.stringify({
      portfolio_id: portfolioId,
      ...(candidateIds?.length ? { candidate_ids: candidateIds } : {}),
    }),
  });
}

export function postSettle() {
  return request<Json>("/v1/runs/settle", {
    method: "POST",
    body: JSON.stringify({}),
  });
}

export function postFullDay(fixture = "day001") {
  return request<Json>("/v1/runs/full-day", {
    method: "POST",
    body: JSON.stringify({ fixture }),
  });
}

export function getCandidates() {
  return request<Json>("/v1/candidates");
}

/** Session-backed last competition packet (fallback if GET /candidates empty). */
const COMPETE_KEY = "holler.operator.lastCompetition";

export function cacheCompetition(packet: Json): void {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.setItem(COMPETE_KEY, JSON.stringify(packet));
  } catch {
    /* quota / private mode */
  }
}

export function readCachedCompetition(): Json | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(COMPETE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as Json;
  } catch {
    return null;
  }
}

export function candidateKey(c: {
  strategy_id?: unknown;
  market_id?: unknown;
  selection?: unknown;
}): string {
  return `${String(c.strategy_id ?? "")}|${String(c.market_id ?? "")}|${String(c.selection ?? "")}`;
}

export function fieldOrDash(
  value: unknown,
  reason = "not on dashboard packet",
): { text: string; reason?: string } {
  if (value === null || value === undefined || value === "") {
    return { text: "—", reason };
  }
  if (typeof value === "object") {
    try {
      return { text: JSON.stringify(value) };
    } catch {
      return { text: "—", reason: "unserializable" };
    }
  }
  return { text: String(value) };
}
