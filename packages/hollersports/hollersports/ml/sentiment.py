"""Lightweight offline sentiment scorer (advisory research only).

No network. Pure stdlib lexicon. Never invents text — returns 0.0 when no
content is provided. Optional market fields: ``sentiment_score``, ``headline``,
``news_snippet``, ``text``.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

# Tiny sports-betting lexicon (weights in [-1, 1]). Deterministic stub for feeds.
_POS = frozenset(
    {
        "win",
        "wins",
        "winning",
        "hot",
        "surge",
        "surging",
        "dominant",
        "healthy",
        "return",
        "returns",
        "boost",
        "strong",
        "favorite",
        "favourable",
        "favorable",
        "confident",
        "momentum",
        "breakout",
        "underrated",
    }
)
_NEG = frozenset(
    {
        "loss",
        "lose",
        "losing",
        "injury",
        "injured",
        "out",
        "doubtful",
        "questionable",
        "cold",
        "slump",
        "slumping",
        "weak",
        "struggle",
        "struggles",
        "suspended",
        "rest",
        "resting",
        "blowout",
        "overrated",
        "fade",
        "fading",
    }
)

_TOKEN = re.compile(r"[a-z0-9']+")


def score_text_sentiment(text: str | None) -> float:
    """Return score in [-1.0, 1.0]. Empty/missing text → 0.0 (fail soft)."""
    if not text or not str(text).strip():
        return 0.0
    tokens = _TOKEN.findall(str(text).lower())
    if not tokens:
        return 0.0
    score = 0.0
    hits = 0
    for t in tokens:
        if t in _POS:
            score += 1.0
            hits += 1
        elif t in _NEG:
            score -= 1.0
            hits += 1
    if hits == 0:
        return 0.0
    # Average hit polarity, clamped
    raw = score / hits
    return max(-1.0, min(1.0, raw))


def resolve_market_sentiment(market: Mapping[str, Any]) -> float:
    """Prefer explicit sentiment_score; else score text fields; else 0.0.

    Explicit scores may be in [-1, 1] or [0, 1]; stored as-is after clamp to [-1, 1].
    """
    raw = market.get("sentiment_score")
    if raw is not None:
        try:
            v = float(raw)
            return max(-1.0, min(1.0, v))
        except (TypeError, ValueError):
            pass
    for key in ("headline", "news_snippet", "text", "commentary"):
        t = market.get(key)
        if t:
            return score_text_sentiment(str(t))
    return 0.0


def enrich_markets_sentiment(
    markets: list[dict[str, Any]] | list[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Copy markets with sentiment_score filled when derivable (never invents text)."""
    out: list[dict[str, Any]] = []
    for m in markets:
        if not isinstance(m, Mapping):
            continue
        row = dict(m)
        if row.get("sentiment_score") is None:
            s = resolve_market_sentiment(row)
            if s != 0.0 or any(row.get(k) for k in ("headline", "news_snippet", "text")):
                row["sentiment_score"] = s
                row.setdefault(
                    "sentiment_source",
                    "lexicon" if any(row.get(k) for k in ("headline", "news_snippet", "text", "commentary")) else "explicit_or_zero",
                )
        out.append(row)
    return out
