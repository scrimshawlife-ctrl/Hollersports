"""PyTorch temporal models: axial + TransformerEncoder (Track G).

Optional: ``pip install -e "packages/hollersports[torch]"``.

Architectures:
  * ``axial_small`` — d=32, 2 layers (v0.4 default)
  * ``axial_large`` — d=64, 4 layers, 8 heads
  * ``transformer`` — nn.TransformerEncoder over time
  * ``transformer_dist`` — transformer + categorical total bins (CRPS)

Advisory only — no capital/execution authority.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from hollersports.ml.axial_stub import markets_to_sequence
from hollersports.ml.crps import crps_categorical, expected_bin
from hollersports.ml.features import FEATURE_NAMES, build_feature_rows
from hollersports.schemas.hashing import packet_hash

MODEL_KIND = "axial_torch_v1"
DEFAULT_D_MODEL = 32
DEFAULT_N_HEADS = 4
DEFAULT_N_LAYERS = 2
DEFAULT_MAX_LEN = 64
DEFAULT_N_TOTAL_BINS = 11  # totals 0..10+

ARCH_PRESETS: dict[str, dict[str, Any]] = {
    "axial_small": {
        "arch": "axial",
        "d_model": 32,
        "n_heads": 4,
        "n_layers": 2,
        "distributional": False,
    },
    "axial_large": {
        "arch": "axial",
        "d_model": 64,
        "n_heads": 8,
        "n_layers": 4,
        "distributional": False,
    },
    "transformer": {
        "arch": "transformer",
        "d_model": 64,
        "n_heads": 8,
        "n_layers": 4,
        "distributional": False,
    },
    "transformer_dist": {
        "arch": "transformer",
        "d_model": 64,
        "n_heads": 8,
        "n_layers": 4,
        "distributional": True,
        "n_total_bins": DEFAULT_N_TOTAL_BINS,
    },
}


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


def resolve_arch_preset(name: str | None) -> dict[str, Any]:
    key = str(name or "axial_small").lower().strip()
    if key not in ARCH_PRESETS:
        raise ValueError(
            f"unknown_arch:{name!r}; choose from {sorted(ARCH_PRESETS)}"
        )
    return dict(ARCH_PRESETS[key])


def build_temporal_module(
    n_features: int,
    *,
    arch: str = "axial",
    d_model: int = DEFAULT_D_MODEL,
    n_heads: int = DEFAULT_N_HEADS,
    n_layers: int = DEFAULT_N_LAYERS,
    max_len: int = DEFAULT_MAX_LEN,
    dropout: float = 0.1,
    distributional: bool = False,
    n_total_bins: int = DEFAULT_N_TOTAL_BINS,
):
    """Build axial or TransformerEncoder temporal net."""
    torch, nn, F = _require_torch()
    while d_model % n_heads != 0 and n_heads > 1:
        n_heads -= 1
    arch_l = str(arch or "axial").lower()

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
            self.time_to_feat = nn.Linear(d_model, d_model)
            self.feat_query = nn.Parameter(torch.randn(1, n_features, d_model) * 0.02)

        def forward(self, x: Any) -> Any:
            t_out, _ = self.time_attn(x, x, x, need_weights=False)
            x = self.norm_t(x + t_out)
            b = x.shape[0]
            q = self.feat_query.expand(b, -1, -1)
            kv = self.time_to_feat(x)
            f_out, _ = self.feat_attn(q, kv, kv, need_weights=False)
            f_out = self.norm_f(q + f_out)
            x = x + f_out.mean(dim=1, keepdim=True)
            return self.norm_ff(x + self.ff(x))

    class TemporalNet(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.n_features = n_features
            self.d_model = d_model
            self.max_len = max_len
            self.arch = arch_l
            self.distributional = bool(distributional)
            self.n_total_bins = int(n_total_bins)
            self.input_proj = nn.Linear(n_features, d_model)
            self.pos = nn.Parameter(torch.zeros(1, max_len, d_model))
            nn.init.normal_(self.pos, std=0.02)
            if arch_l == "transformer":
                layer = nn.TransformerEncoderLayer(
                    d_model=d_model,
                    nhead=n_heads,
                    dim_feedforward=d_model * 4,
                    dropout=dropout,
                    batch_first=True,
                    activation="gelu",
                )
                self.encoder = nn.TransformerEncoder(layer, num_layers=n_layers)
                self.layers = None
            else:
                self.layers = nn.ModuleList([AxialLayer() for _ in range(n_layers)])
                self.encoder = None
            self.head = nn.Linear(d_model, 1)
            self.dist_head = (
                nn.Linear(d_model, self.n_total_bins) if self.distributional else None
            )
            self.meta = {
                "kind": MODEL_KIND,
                "arch": arch_l,
                "n_features": n_features,
                "d_model": d_model,
                "n_heads": n_heads,
                "n_layers": n_layers,
                "max_len": max_len,
                "distributional": self.distributional,
                "n_total_bins": self.n_total_bins if self.distributional else 0,
            }

        def encode(self, x: Any) -> Any:
            _b, t, _f = x.shape
            if t > self.max_len:
                x = x[:, -self.max_len :, :]
                t = self.max_len
            h = self.input_proj(x) + self.pos[:, :t, :]
            if self.encoder is not None:
                h = self.encoder(h)
            else:
                assert self.layers is not None
                for layer in self.layers:
                    h = layer(h)
            return h

        def forward(self, x: Any) -> Any:
            h = self.encode(x)
            return self.head(h[:, -1, :]).squeeze(-1)

        def forward_dist(self, x: Any) -> Any:
            if self.dist_head is None:
                raise RuntimeError("model is not distributional")
            h = self.encode(x)
            return self.dist_head(h[:, -1, :])

        def predict_proba(self, x: Any) -> Any:
            return torch.sigmoid(self.forward(x))

        def predict_total_probs(self, x: Any) -> Any:
            return F.softmax(self.forward_dist(x), dim=-1)

    return TemporalNet()


# Back-compat alias
def build_axial_module(n_features: int, **kwargs: Any):
    return build_temporal_module(n_features, arch="axial", **kwargs)


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
) -> tuple[list[list[list[float]]], list[int], list[int | None]]:
    """Labeled windows; also derive soft total-bin labels from final_score if present."""
    X_seq: list[list[list[float]]] = []
    y: list[int] = []
    y_total: list[int | None] = []
    for day in fixture_days:
        rows = build_feature_rows([day], require_labels=False)
        rows = sorted(rows, key=lambda r: str(r.get("market_id") or ""))
        # attach labels from results via build_feature_rows y
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
            # total bins unknown from moneyline-only fixtures → None
            y_total.append(None)
    return X_seq, y, y_total


def sequences_from_store_and_fixtures(
    fixture_days: Sequence[Path | str],
    *,
    data_root: Path | str | None = None,
    fixture_sequence_path: Path | str | None = None,
) -> tuple[list[list[list[float]]], list[int], list[int | None]]:
    """Merge fixture day windows, optional sequence store, optional fixture sequences file."""
    X, y, yt = sequences_from_fixture_days(fixture_days)
    if data_root is not None:
        from hollersports.sources.sequence_store import sequences_by_line_key

        for _key, seq in sequences_by_line_key(data_root, min_len=2).items():
            # unlabeled multi-poll — skip for supervised unless we have y
            # use last feature implied proxy as weak label if length allows
            if len(seq) < 2:
                continue
            # weak: if last implied > 0.55 treat as 1
            last = seq[-1]
            imp = float(last[0]) if last else 0.5
            X.append(seq)
            y.append(1 if imp >= 0.55 else 0)
            yt.append(None)
    if fixture_sequence_path is not None and Path(fixture_sequence_path).is_file():
        from hollersports.sources.sequence_store import load_fixture_sequences

        for item in load_fixture_sequences(fixture_sequence_path):
            x_seq = item.get("x_seq") or item.get("sequence")
            if not isinstance(x_seq, list) or len(x_seq) < 2:
                continue
            try:
                seq = [[float(v) for v in row] for row in x_seq]
            except (TypeError, ValueError):
                continue
            if "y" not in item and "label" not in item:
                continue
            lab = item.get("y", item.get("label"))
            X.append(seq)
            y.append(int(lab))
            tb = item.get("y_total")
            yt.append(int(tb) if tb is not None else None)
    return X, y, yt


def train_axial(
    fixture_days: Sequence[Path | str],
    *,
    out_dir: Path | str,
    epochs: int = 40,
    lr: float = 1e-3,
    seed: int = 42,
    arch_preset: str = "axial_small",
    d_model: int | None = None,
    n_heads: int | None = None,
    n_layers: int | None = None,
    data_root: Path | str | None = None,
    fixture_sequence_path: Path | str | None = None,
) -> dict[str, Any]:
    """Train temporal model; write weights + meta; optional model card."""
    torch, _nn, F = _require_torch()
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    preset = resolve_arch_preset(arch_preset)
    arch = str(preset["arch"])
    d_model = int(d_model if d_model is not None else preset["d_model"])
    n_heads = int(n_heads if n_heads is not None else preset["n_heads"])
    n_layers = int(n_layers if n_layers is not None else preset["n_layers"])
    distributional = bool(preset.get("distributional"))
    n_total_bins = int(preset.get("n_total_bins") or DEFAULT_N_TOTAL_BINS)

    X_seq, y, y_total = sequences_from_store_and_fixtures(
        fixture_days,
        data_root=data_root,
        fixture_sequence_path=fixture_sequence_path,
    )
    if len(X_seq) < 2:
        raise ValueError(f"need >=2 labeled sequences, got {len(X_seq)}")

    n_features = len(X_seq[0][0])
    torch.manual_seed(seed)
    model = build_temporal_module(
        n_features,
        arch=arch,
        d_model=d_model,
        n_heads=n_heads,
        n_layers=n_layers,
        distributional=distributional,
        n_total_bins=n_total_bins,
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

    # Synthetic total bins for dist head when missing: bin from implied * 10
    yt_list: list[int] = []
    for i, yt in enumerate(y_total):
        if yt is not None:
            yt_list.append(max(0, min(n_total_bins - 1, int(yt))))
        else:
            imp = float(X_seq[i][-1][0]) if X_seq[i] else 0.5
            yt_list.append(max(0, min(n_total_bins - 1, int(round(imp * (n_total_bins - 1))))))
    ytb = torch.tensor(yt_list, dtype=torch.long)

    history: list[float] = []
    for _ in range(epochs):
        opt.zero_grad()
        logits = model(xb)
        loss = F.binary_cross_entropy_with_logits(logits, yb)
        if distributional and model.dist_head is not None:
            dist_logits = model.forward_dist(xb)
            loss = loss + 0.5 * F.cross_entropy(dist_logits, ytb)
        loss.backward()
        opt.step()
        history.append(float(loss.item()))

    model.eval()
    with torch.no_grad():
        probs = model.predict_proba(xb)
        brier = float(((probs - yb) ** 2).mean().item())
        acc = float(((probs >= 0.5).float() == yb).float().mean().item())
        crps_mean = None
        if distributional and model.dist_head is not None:
            dist_p = model.predict_total_probs(xb)
            crps_vals = [
                crps_categorical(dist_p[i].tolist(), int(ytb[i].item()))
                for i in range(dist_p.shape[0])
            ]
            crps_mean = float(sum(crps_vals) / len(crps_vals)) if crps_vals else None

    weights_path = out / "axial_torch.pt"
    meta_path = out / "axial_torch.meta.json"
    torch.save({"state_dict": model.state_dict(), "meta": model.meta}, weights_path)

    meta: dict[str, Any] = {
        "kind": MODEL_KIND,
        "arch": arch,
        "arch_preset": arch_preset,
        "weights_path": weights_path.name,
        "n_features": n_features,
        "feature_names": list(FEATURE_NAMES)[:n_features],
        "d_model": d_model,
        "n_heads": n_heads,
        "n_layers": n_layers,
        "max_len": DEFAULT_MAX_LEN,
        "distributional": distributional,
        "n_total_bins": n_total_bins if distributional else 0,
        "train_n": len(y),
        "epochs": epochs,
        "seed": seed,
        "metrics": {
            "train_bce_last": history[-1] if history else None,
            "train_brier": brier,
            "train_acc": acc,
            "train_crps": crps_mean,
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

    # G4: model card next to weights
    card_paths: dict[str, str] = {}
    try:
        from hollersports.ml.model_card import write_model_card

        # synthesize ensemble-like path for card? write lightweight card JSON
        card_dir = out / "model_cards"
        card_dir.mkdir(parents=True, exist_ok=True)
        card = {
            "schema_version": "HollerModelCard.v1",
            "model_id": meta["model_id"],
            "kind": MODEL_KIND,
            "arch_preset": arch_preset,
            "metrics": meta["metrics"],
            "capital_authority": False,
            "execution_authority": False,
            "mode": "ADVISORY_ONLY",
            "markdown": (
                f"# Model card: `{meta['model_id']}`\n\n"
                f"- arch: `{arch_preset}`\n"
                f"- train_brier: `{brier}`\n"
                f"- train_crps: `{crps_mean}`\n"
                f"- train_n: `{len(y)}`\n\n"
                "Advisory only — no real money.\n"
            ),
        }
        md_path = card_dir / f"{meta['model_id']}.md"
        json_path = card_dir / f"{meta['model_id']}.json"
        md_path.write_text(card["markdown"], encoding="utf-8")
        json_path.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        card_paths = {"model_card_md": str(md_path), "model_card_json": str(json_path)}
    except Exception:  # noqa: BLE001
        card_paths = {}

    return {
        **meta,
        "weights_path": str(weights_path),
        "meta_path": str(meta_path),
        **card_paths,
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
    model = build_temporal_module(
        int(meta["n_features"]),
        arch=str(meta.get("arch") or "axial"),
        d_model=int(meta.get("d_model") or DEFAULT_D_MODEL),
        n_heads=int(meta.get("n_heads") or DEFAULT_N_HEADS),
        n_layers=int(meta.get("n_layers") or DEFAULT_N_LAYERS),
        max_len=int(meta.get("max_len") or DEFAULT_MAX_LEN),
        distributional=bool(meta.get("distributional")),
        n_total_bins=int(meta.get("n_total_bins") or DEFAULT_N_TOTAL_BINS),
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
            model = build_temporal_module(n_features, arch="axial")
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
        total_probs = None
        expected_total = None
        if bool(meta.get("distributional")) and getattr(model, "dist_head", None) is not None:
            tp = model.predict_total_probs(xb)[0].tolist()
            total_probs = tp
            expected_total = expected_bin(tp)

    packet: dict[str, Any] = {
        "schema_version": "HollerAxialTorch.v1",
        "status": "COMPUTED" if trained else "UNSUPERVISED_FORWARD",
        "kind": MODEL_KIND,
        "arch": meta.get("arch"),
        "arch_preset": meta.get("arch_preset"),
        "trained": trained,
        "seq_len": len(padded),
        "n_features": n_features,
        "last_features": last,
        "logit": logit,
        "probability": proba,
        "total_probs": total_probs,
        "expected_total": expected_total,
        "model_id": meta.get("model_id") or meta.get("artifact_hash"),
        "metrics": meta.get("metrics"),
        "note": "pytorch_temporal_axial_or_transformer",
        "capital_authority": False,
        "execution_authority": False,
        "authority": "SHADOW_ONLY",
        "mode": "ADVISORY_ONLY",
    }
    packet["packet_hash"] = packet_hash(
        {k: v for k, v in packet.items() if k not in {"packet_hash", "last_features", "total_probs"}}
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
