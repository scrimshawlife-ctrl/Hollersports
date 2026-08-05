"""Generate Obsidian/Notion-ready model cards from ensemble artifacts (advisory)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from hollersports.ml.calibrate import load_ensemble
from hollersports.ml.features import FEATURE_NAMES
from hollersports.ml.train import load_model
from hollersports.schemas.hashing import packet_hash


def _resolve_base_model(ensemble_path: Path, art: Mapping[str, Any]) -> dict[str, Any] | None:
    models = art.get("models") or []
    if not models:
        return None
    rel = str((models[0] or {}).get("path") or "")
    if not rel:
        return None
    p = Path(rel)
    if not p.is_file():
        p = ensemble_path.parent / Path(rel).name
    if not p.is_file():
        return None
    try:
        return load_model(p)
    except (OSError, ValueError, ImportError):
        return None


def build_model_card(
    ensemble_path: Path | str,
    *,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Structured model card + markdown body. Fail closed if ensemble missing."""
    ep = Path(ensemble_path)
    if not ep.is_file():
        raise FileNotFoundError(f"ensemble not found: {ep}")
    art = load_ensemble(ep)
    model = _resolve_base_model(ep, art) or {}
    model_id = str(
        (art.get("models") or [{}])[0].get("model_id")
        or model.get("model_id")
        or ep.stem
    )
    metrics = dict(art.get("metrics") or model.get("metrics") or {})
    data_hash = str(art.get("data_hash") or model.get("data_hash") or "")
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    card: dict[str, Any] = {
        "schema_version": "HollerModelCard.v1",
        "model_id": model_id,
        "ensemble_id": art.get("ensemble_id"),
        "date": now,
        "data_hash": data_hash,
        "artifact_hash": art.get("artifact_hash"),
        "temperature": art.get("temperature"),
        "metrics": metrics,
        "features_used": list(model.get("feature_names") or FEATURE_NAMES),
        "model_kind": model.get("kind") or "unknown",
        "ensemble_path": str(ep.resolve()),
        "provenance": {
            **dict(model.get("provenance") or {}),
            "ensemble_provenance": {
                "capital_authority": False,
                "execution_authority": False,
                "status": "ADVISORY_ONLY",
            },
        },
        "capital_authority": False,
        "execution_authority": False,
        "authority": "SHADOW_ONLY",
        "mode": "ADVISORY_ONLY",
    }
    if extra:
        card["extra"] = dict(extra)
    card["packet_hash"] = packet_hash(
        {k: v for k, v in card.items() if k != "packet_hash"}
    )
    card["markdown"] = render_model_card_markdown(card)
    return card


def render_model_card_markdown(card: Mapping[str, Any]) -> str:
    """YAML-frontmatter markdown for Obsidian / internal docs."""
    metrics = card.get("metrics") or {}
    features = card.get("features_used") or []
    fm = {
        "model_id": card.get("model_id"),
        "date": card.get("date"),
        "data_hash": card.get("data_hash"),
        "metrics": {
            "train_brier": metrics.get("train_brier"),
            "val_brier": metrics.get("val_brier"),
            "val_nll": metrics.get("val_nll"),
            "temperature": card.get("temperature"),
        },
        "features_used": list(features),
        "provenance": {
            "ensemble_id": card.get("ensemble_id"),
            "artifact_hash": card.get("artifact_hash"),
            "model_kind": card.get("model_kind"),
        },
        "capital_authority": False,
        "execution_authority": False,
        "status": "ADVISORY_ONLY",
    }
    yaml_body = json.dumps(fm, indent=2, sort_keys=True)
    # Use YAML-ish frontmatter with JSON block for stable parsing without PyYAML dep
    lines = [
        "---",
        f"model_id: {fm['model_id']!r}",
        f"date: {fm['date']!r}",
        f"data_hash: {fm['data_hash']!r}",
        f"model_kind: {fm['provenance']['model_kind']!r}",
        "capital_authority: false",
        "execution_authority: false",
        "status: ADVISORY_ONLY",
        "---",
        "",
        f"# Model card: `{card.get('model_id')}`",
        "",
        "Advisory only — paper simulation. No real money. No book placement.",
        "",
        "## Metrics",
        "",
        f"- train_brier: `{metrics.get('train_brier')}`",
        f"- val_brier: `{metrics.get('val_brier')}`",
        f"- val_nll: `{metrics.get('val_nll')}`",
        f"- temperature: `{card.get('temperature')}`",
        f"- train_n / val_n: `{metrics.get('train_n')}` / `{metrics.get('val_n')}`",
        "",
        "## Features",
        "",
    ]
    for f in features:
        lines.append(f"- `{f}`")
    lines.extend(
        [
            "",
            "## Provenance",
            "",
            f"- ensemble_id: `{card.get('ensemble_id')}`",
            f"- artifact_hash: `{card.get('artifact_hash')}`",
            f"- data_hash: `{card.get('data_hash')}`",
            f"- packet_hash: `{card.get('packet_hash')}`",
            f"- ensemble_path: `{card.get('ensemble_path')}`",
            "",
            "## Structured frontmatter (JSON)",
            "",
            "```json",
            yaml_body,
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_model_card(
    ensemble_path: Path | str,
    *,
    out_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Write markdown + JSON card next to ensemble or under out_dir."""
    ep = Path(ensemble_path)
    card = build_model_card(ep)
    dest = Path(out_dir) if out_dir else ep.parent / "model_cards"
    dest.mkdir(parents=True, exist_ok=True)
    mid = str(card["model_id"])
    md_path = dest / f"{mid}.md"
    json_path = dest / f"{mid}.json"
    md_path.write_text(card["markdown"], encoding="utf-8")
    # JSON without huge markdown duplication optional — keep markdown field
    json_path.write_text(
        json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    card["written_md"] = str(md_path)
    card["written_json"] = str(json_path)
    return card
