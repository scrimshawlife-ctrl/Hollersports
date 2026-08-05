"""PyTorch axial temporal model (arXiv 2511.18730-inspired).

Optional: ``pip install -e "packages/hollersports[torch]"``.

Factorized attention over time then feature-axis tokens. Advisory only.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from hollersports.ml.axial_stub import markets_to_sequence
from hollersports.ml.features import FEATURE_NAMES, build_feature_rows
from hollersports.schemas.hashing import packet_hash

MODEL_KIND = "axial_torch_v1"
DEFAULT_D_MODEL = 32
DEFAULT_N_HEADS = 4
DEFAULT_N_LAYERS = 2
DEFAULT_MAX_LEN = 64


def torch_available() -> bool:
    try:
        import torch  # noqa: F401

        return True
    except ImportError:
        return False


def _require_torch():
    try:
        import torch
        import torch.nn as nn
        import torch.nn.functional as F
    except ImportError as exc:
        raise ImportError(
            'PyTorch required: pip install -e "packages/hollersports[torch]"'
        ) from exc
    return torch, nn, F


def build_axial_module(
    n_features: int,
    *,
    d_model: int = DEFAULT_D_MODEL,
    n_heads: int = DEFAULT_N_HEADS,
    n_layers: int = DEFAULT_N_LAYERS,
    max_len: int = DEFAULT_MAX_LEN,
    dropout: float = 0.1,
):
    """Return AxialTemporalNet nn.Module."""
    torch, nn, F = _require_torch()

    # Heads must divide d_model
    while d_model % n_heads != 0 and n_heads > 1:
        n_heads -= 1

    class AxialLayer(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.time_attn = nn.MultiheadAttention(
                d_model, n_heads, dropout=dropout, batch_first=True
            )
            self.feat_attn = nn.MultiheadAttention(
                d_model, n_heads, dropout=dropout, batch_first=True
            )
            self.norm_t = nn.LayerNorm(d_model)
            self.norm_f = nn.LayerNorm(d_model)
            self.ff = nn.Sequential(
                nn.Linear(d_model, d_model * 2),
                nn.GELU(),
                nn.Dropout(dropout),
                nn.Linear(d_model * 2, d_model),
                nn.Dropout(dropout),
            )
            self.norm_ff = nn.LayerNorm(d_model)
            # Produce F feature tokens of dim d_model from the time sequence
            self.time_to_feat = nn.Linear(d_model, d_model)
            self.feat_query = nn.Parameter(torch.randn(1, n_features, d_model) * 0.02)

        def forward(self, x: Any) -> Any:
            # --- Time axis: self-attention over T ---
            t_out, _ = self.time_attn(x, x, x, need_weights=False)
            x = self.norm_t(x + t_out)

            # --- Feature axis: cross-attend F learned queries over time keys ---
            # queries: [B, F, D], keys/values from time tokens [B, T, D]
            b = x.shape[0]
            q = self.feat_query.expand(b, -1, -1)
            kv = self.time_to_feat(x)
            f_out, _ = self.feat_attn(q, kv, kv, need_weights=False)
            f_out = self.norm_f(q + f_out)
            # Pool feature tokens → context, residual into every time step
            feat_ctx = f_out.mean(dim=1, keepdim=True)  # [B, 1, D]
            x = x + feat_ctx

            x = self.norm_ff(x + self.ff(x))
            return x

    class AxialTemporalNet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.n_features = n_features
            self.d_model = d_model
            self.max_len = max_len
            self.input_proj = nn.Linear(n_features, d_model)
            self.pos = nn.Parameter(torch.zeros(1, max_len, d_model))
            nn.init.normal_(self.pos, std=0.02)
            self.layers = nn.ModuleList([AxialLayer() for _ in range(n_layers)])
            self.head = nn.Linear(d_model, 1)
            self.meta = {
                "kind": MODEL_KIND,
                "n_features": n_features,
                "d_model": d_model,
                "n_heads": n_heads,
                "n_layers": n_layers,
                "max_len": max_len,
            }

        def encode(self, x: Any) -> Any:
            # x: [B, T, F]
            _b, t, _f = x.shape
            if t > self.max_len:
                x = x[:, -self.max_len :, :]
                t = self.max_len
            h = self.input_proj(x)
            h = h + self.pos[:, :t, :]
            for layer in self.layers:
                h = layer(h)
            return h

        def forward(self, x: Any) -> Any:
            h = self.encode(x)
            return self.head(h[:, -1, :]).squeeze(-1)

        def predict_proba(self, x: Any) -> Any:
            return torch.sigmoid(self.forward(x))

    return AxialTemporalNet()


def _pad_sequence(
    seq: Sequence[Sequence[float]], n_features: int, max_len: int
) -> list[list[float]]:
    rows: list[list[float]] = []
    for row in list(seq)[-max_len:]:
        r: list[float] = []
        for j in range(n_features):
            if j < len(row):
                try:
                    r.append(float(row[j]))
                except (TypeError, ValueError):
                    r.append(0.0)
            else:
                r.append(0.0)
        rows.append(r)
    if not rows:
        rows = [[0.0] * n_features]
    return rows


def sequences_from_fixture_days(
    fixture_days: Sequence[Path | str],
    *,
    min_len: int = 2,
) -> tuple[list[list[list[float]]], list[int]]:
    """Labeled windows ending at each market within a fixture day."""
    X_seq: list[list[list[float]]] = []
    y: list[int] = []
    for day in fixture_days:
        rows = build_feature_rows([day], require_labels=False)
        rows = sorted(rows, key=lambda r: str(r.get("market_id") or ""))
        xs = [r["x"] for r in rows if "x" in r]
        labels = [r.get("y") for r in rows]
        for i, lab in enumerate(labels):
            if lab is None:
                continue
            start = max(0, i - 7)
            window = list(xs[start : i + 1])
            if not window:
                continue
            while len(window) < min_len:
                window = [window[0]] + window
            X_seq.append(window)
            y.append(int(lab))
    return X_seq, y


def train_axial(
    fixture_days: Sequence[Path | str],
    *,
    out_dir: Path | str,
    epochs: int = 40,
    lr: float = 1e-3,
    seed: int = 42,
    d_model: int = DEFAULT_D_MODEL,
    n_heads: int = DEFAULT_N_HEADS,
    n_layers: int = DEFAULT_N_LAYERS,
) -> dict[str, Any]:
    """Train axial model; write ``axial_torch.pt`` + ``axial_torch.meta.json``."""
    torch, _nn, F = _require_torch()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    X_seq, y = sequences_from_fixture_days(fixture_days)
    if len(X_seq) < 2:
        raise ValueError(f"need >=2 labeled sequences, got {len(X_seq)}")

    n_features = len(X_seq[0][0])
    torch.manual_seed(seed)
    model = build_axial_module(
        n_features, d_model=d_model, n_heads=n_heads, n_layers=n_layers
    )
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    model.train()

    max_t = min(max(len(s) for s in X_seq), DEFAULT_MAX_LEN)
    tensors = []
    for s in X_seq:
        t = torch.tensor(_pad_sequence(s, n_features, max_t), dtype=torch.float32)
        if t.shape[0] < max_t:
            pad = torch.zeros(max_t - t.shape[0], n_features)
            t = torch.cat([pad, t], dim=0)
        tensors.append(t)
    xb = torch.stack(tensors, dim=0)
    yb = torch.tensor(y, dtype=torch.float32)

    history: list[float] = []
    for _ in range(epochs):
        opt.zero_grad()
        logits = model(xb)
        loss = F.binary_cross_entropy_with_logits(logits, yb)
        loss.backward()
        opt.step()
        history.append(float(loss.item()))

    model.eval()
    with torch.no_grad():
        probs = model.predict_proba(xb)
        brier = float(((probs - yb) ** 2).mean().item())
        acc = float(((probs >= 0.5).float() == yb).float().mean().item())

    weights_path = out / "axial_torch.pt"
    meta_path = out / "axial_torch.meta.json"
    torch.save({"state_dict": model.state_dict(), "meta": model.meta}, weights_path)

    meta: dict[str, Any] = {
        "kind": MODEL_KIND,
        "weights_path": weights_path.name,
        "n_features": n_features,
        "feature_names": list(FEATURE_NAMES)[:n_features],
        "d_model": d_model,
        "n_heads": n_heads,
        "n_layers": n_layers,
        "max_len": DEFAULT_MAX_LEN,
        "train_n": len(y),
        "epochs": epochs,
        "seed": seed,
        "metrics": {
            "train_bce_last": history[-1] if history else None,
            "train_brier": brier,
            "train_acc": acc,
        },
        "train_days": [str(d) for d in fixture_days],
        "capital_authority": False,
        "execution_authority": False,
        "status": "ADVISORY_ONLY",
    }
    meta["artifact_hash"] = packet_hash(
        {k: v for k, v in meta.items() if k != "artifact_hash"}
    )
    meta["model_id"] = f"axial_{meta['artifact_hash'][:10]}"
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        **meta,
        "weights_path": str(weights_path),
        "meta_path": str(meta_path),
    }


def load_axial(meta_path: Path | str) -> tuple[Any, dict[str, Any]]:
    torch, _nn, _F = _require_torch()
    mp = Path(meta_path)
    meta = json.loads(mp.read_text(encoding="utf-8"))
    if not isinstance(meta, dict):
        raise ValueError("invalid axial meta")
    weights = mp.parent / str(meta.get("weights_path") or "axial_torch.pt")
    if not weights.is_file():
        alt = Path(str(meta.get("weights_path") or ""))
        if alt.is_file():
            weights = alt
        else:
            raise FileNotFoundError(f"weights not found: {weights}")
    model = build_axial_module(
        int(meta["n_features"]),
        d_model=int(meta.get("d_model") or DEFAULT_D_MODEL),
        n_heads=int(meta.get("n_heads") or DEFAULT_N_HEADS),
        n_layers=int(meta.get("n_layers") or DEFAULT_N_LAYERS),
        max_len=int(meta.get("max_len") or DEFAULT_MAX_LEN),
    )
    try:
        blob = torch.load(weights, map_location="cpu", weights_only=True)
    except TypeError:
        blob = torch.load(weights, map_location="cpu")
    state = blob["state_dict"] if isinstance(blob, dict) and "state_dict" in blob else blob
    model.load_state_dict(state)
    model.eval()
    return model, meta


def score_sequence_torch(
    sequence: Sequence[Sequence[float]],
    *,
    model_meta_path: Path | str | None = None,
    model: Any | None = None,
    meta: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Score sequence with trained axial net (or untrained forward for smoke)."""
    torch, _nn, _F = _require_torch()
    if not sequence:
        return {
            "schema_version": "HollerAxialTorch.v1",
            "status": "NOT_COMPUTABLE",
            "reason": "empty_sequence",
            "kind": MODEL_KIND,
            "capital_authority": False,
            "execution_authority": False,
            "authority": "SHADOW_ONLY",
            "mode": "ADVISORY_ONLY",
        }

    trained = False
    if model is None:
        if model_meta_path is not None and Path(model_meta_path).is_file():
            model, meta_loaded = load_axial(model_meta_path)
            meta = meta_loaded
            trained = True
        else:
            n_features = max(len(r) for r in sequence)
            model = build_axial_module(n_features)
            meta = dict(model.meta)
            trained = False
    assert meta is not None
    n_features = int(meta.get("n_features") or max(len(r) for r in sequence))
    max_len = int(meta.get("max_len") or DEFAULT_MAX_LEN)
    padded = _pad_sequence(sequence, n_features, max_len)
    xb = torch.tensor([padded], dtype=torch.float32)
    model.eval()
    with torch.no_grad():
        h = model.encode(xb)
        last = h[0, -1, :].tolist()
        logit = float(model(xb)[0].item())
        proba = float(1.0 / (1.0 + math.exp(-logit)))

    packet: dict[str, Any] = {
        "schema_version": "HollerAxialTorch.v1",
        "status": "COMPUTED" if trained else "UNSUPERVISED_FORWARD",
        "kind": MODEL_KIND,
        "trained": trained,
        "seq_len": len(padded),
        "n_features": n_features,
        "last_features": last,
        "logit": logit,
        "probability": proba,
        "model_id": meta.get("model_id") or meta.get("artifact_hash"),
        "metrics": meta.get("metrics"),
        "note": "pytorch_axial_factorized_attention",
        "capital_authority": False,
        "execution_authority": False,
        "authority": "SHADOW_ONLY",
        "mode": "ADVISORY_ONLY",
    }
    packet["packet_hash"] = packet_hash(
        {k: v for k, v in packet.items() if k != "packet_hash"}
    )
    return packet


def score_markets_torch(
    markets: Sequence[Mapping[str, Any]],
    *,
    model_meta_path: Path | str | None = None,
) -> dict[str, Any]:
    return score_sequence_torch(
        markets_to_sequence(markets), model_meta_path=model_meta_path
    )
