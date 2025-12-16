# ABX-Core: Scorer-Under Eligibility Gate

**Deterministic, typed, testable module for filtering PTS-UNDER props**

## Overview

The Scorer-Under Gate is a multi-signal filter designed to reduce miss-rate on scorer-under bets by only allowing picks when sufficient suppression indicators are present.

### The Problem

Betting on player points UNDER lines across all games yields inconsistent results. Some scoring environments and game contexts heavily favor unders (low-elasticity arenas, blowouts, concentrated team usage), while others don't.

### The Solution

The gate applies a deterministic filter: **allow PTS-UNDER picks only when ≥2 suppression signals are TRUE**.

## Suppression Signals (v1)

| Signal | Description | Indicator |
|--------|-------------|-----------|
| **Arena Elasticity LOW** | Venue suppresses scoring (e.g., restricted spacing, defensive-minded home advantage) | Arena avg total ≤ 35th percentile |
| **Coach Distribution LOW** | Coach philosophy concentrates usage on fewer players | Team PTS std dev ≥ 65th percentile (high concentration) |
| **Opponent Compression HIGH** | Defense limits individual scoring volume | Opp def rating ≤ threshold OR opp TOV% ≥ threshold |
| **Blowout Risk MODERATE+** | Garbage time, benched starters | \|Spread\| ≥ 8.0 points |
| **Teammate PRA Spike** | When teammate usage spikes, scorer dips (optional, requires multi-leg logs) | User-supplied or computed correlation |

## Quick Start

### 1. Prepare Your Data

Export your historical prop legs to CSV with these columns:

**Required:**
- `date` (YYYY-MM-DD)
- `player`
- `team`
- `opponent`
- `prop_type` (PTS, PRA, AST, etc.)
- `pick` (higher/lower)
- `line` (float)
- `result` (actual stat value)

**Recommended:**
- `hit` (1/0; will be computed if missing)
- `arena`
- `home` (1/0)
- `spread` (negative = favored)
- `total` (game O/U)

See `examples/legs_template.csv` for a sample.

### 2. Run the Backtest

```python
from abraxas.modules.scorer_under_gate import backtest, GateConfig

# Default config
cfg = GateConfig()

# Run backtest
df, report = backtest("legs.csv", cfg)

# View results
print(report)
df.to_csv("legs_with_gate.csv", index=False)
```

Or use the example runner:

```bash
cd examples
python run_backtest.py
```

### 3. Interpret Results

The backtest produces:

**Report dict:**
- `baseline_pts_lower_hit_rate`: Hit rate without gate
- `filtered_pts_lower_hit_rate`: Hit rate with gate applied
- `volume_retained`: Fraction of PTS-lowers allowed through
- `blocked_pts_lower_rows`: Count of blocked picks
- `cfg_hash`: Deterministic config hash for provenance

**Output CSV columns:**
- `gate_eligible`: Boolean (True = allowed, False = blocked)
- `gate_signals`: Count of signals fired (0-5)
- `gate_reasons`: JSON dict of individual signal results
- `gate_provenance`: Deterministic hash of decision

## Configuration

All parameters are deterministic and version-controlled:

```python
cfg = GateConfig(
    # Signal thresholds
    blowout_spread_abs=8.0,                # Blowout if |spread| ≥ 8
    arena_elasticity_low_quantile=0.35,    # Bottom 35% of arenas
    coach_distribution_low_quantile=0.35,  # Bottom 35% distribution

    # Gate rule
    min_signals_required=2,                # Need ≥2 signals to allow

    # Column mapping (customize if your CSV differs)
    col_date="date",
    col_player="player",
    col_team="team",
    # ... see GateConfig docstring for full list
)
```

Changing any parameter changes the `cfg_hash`, ensuring full reproducibility.

## Integration with Bettor Console

The gate produces deterministic "why" strings for display:

```python
from abraxas.modules.scorer_under_gate import scorer_under_gate, GateConfig
import json

# Example: real-time gate check
cfg = GateConfig()
decision = scorer_under_gate(row, cfg)

if not decision.eligible:
    reasons_str = ", ".join(
        k for k, v in decision.reasons.items() if v
    )
    print(f"⚠️  BLOCKED: Only {decision.signals_true}/2 signals detected")
    print(f"   Active: {reasons_str}")
else:
    print(f"✓ ELIGIBLE: {decision.signals_true} suppression signals")
```

Output:
```
⚠️  BLOCKED: Only 1/2 signals detected
   Active: blowout_risk
```

## Testing

Run comprehensive tests:

```bash
pytest tests/test_scorer_under_gate.py -v
```

Test coverage includes:
- Hash determinism and provenance
- Gate logic with all signal combinations
- Feature engineering (arena, coach, opponent proxies)
- Edge cases (missing data, empty datasets, non-PTS props)
- Full backtest pipeline with synthetic data

## Extending the Module

### Adding a New Signal

1. Add threshold to `GateConfig`:
```python
@dataclass(frozen=True)
class GateConfig:
    ...
    my_new_threshold: float = 10.0
```

2. Compute feature in `backtest()`:
```python
df_games["my_new_feature"] = compute_my_feature(df_games, cfg)
```

3. Add signal logic to `scorer_under_gate()`:
```python
my_signal = float(row.get("my_new_feature", 0.5)) >= cfg.my_new_threshold
reasons["my_new_signal"] = my_signal
```

4. Update tests in `test_scorer_under_gate.py`

### Custom Column Mapping

If your CSV uses different column names:

```python
cfg = GateConfig(
    col_player="athlete_name",
    col_team="franchise",
    col_prop="stat_type",
    # ... etc
)
```

## Data Requirements

**Minimum viable:**
- 50+ PTS-UNDER legs for meaningful quantile cuts
- At least a few different arenas/teams for proxy computation

**Recommended:**
- 200+ legs across multiple weeks
- Arena and spread data for better signal quality
- Multiple teams/opponents for distribution proxies

## Provenance & Reproducibility

Every gate decision includes:
- `provenance`: Deterministic hash of config + reasons + signals
- `cfg_hash`: Hash of GateConfig parameters

Same CSV + same config → **identical results**, byte-for-byte.

This enables:
- Audit trails for regulatory compliance
- A/B testing different configurations
- Rollback to previous gate versions
- Debugging discrepancies in production

## Roadmap

**v0.2 (planned):**
- Teammate correlation signal (requires multi-leg parlay logs)
- Arena-specific suppression profiles (Celtics @ TD Garden vs away)
- Time-series features (back-to-back games, rest days)
- Integration with live odds APIs

**v0.3 (planned):**
- ROI-weighted backtest (incorporate payout multipliers)
- Stratified analysis by team/arena/coach
- Confidence intervals via bootstrap resampling
- Web dashboard for interactive exploration

## Support

For issues or questions:
1. Check `examples/run_backtest.py` for usage patterns
2. Review tests in `tests/test_scorer_under_gate.py`
3. Open an issue in the repository

## License

See LICENSE file in repository root.
