# HollerSports

**Sports wagering assistant powered by Abraxas Symbolic Intelligence Engine**

## Overview

HollerSports is a deterministic, typed, and testable framework for sports betting analysis. It uses the Abraxas Symbolic Intelligence Engine with ABX-Core modules to provide data-driven filtering and decision support.

## Features

- **Deterministic Analysis**: All decisions are reproducible with provenance tracking
- **Type-Safe**: Strongly typed data models with immutable configurations
- **Fully Tested**: Comprehensive test coverage for all modules
- **Modular Design**: Drop-in ABX-Core modules for specific betting strategies

## Current Modules

### Scorer-Under Eligibility Gate

A multi-signal filter for PTS-UNDER props that reduces miss-rate by requiring ≥2 suppression signals:

1. **Arena Elasticity LOW** - Venue suppresses scoring
2. **Coach Distribution LOW** - Concentrated usage patterns
3. **Opponent Compression HIGH** - Strong defensive performance
4. **Blowout Risk MODERATE+** - Game script favors bench time
5. **Teammate PRA Spike** - Correlated usage shifts (optional)

See [`abraxas/modules/README.md`](abraxas/modules/README.md) for detailed documentation.

### Contextual Correction Maps (CCM) - **NEW**

Internal calibration layer that learns systematic residual biases by context and applies corrections to projections:

- **Venue effects**: Arena-specific scoring suppression/inflation
- **Coaching philosophy**: Usage concentration, rotation depth, pace
- **Travel factors**: Back-to-back games, timezone shifts, rest days
- **Matchup context**: Defensive rating, pace, opponent schemes

**Key Features:**
- Deterministic shrinkage-based estimation with provenance tracking
- Progressive fallback ladder for robust runtime performance
- Simple toggle: `HOLLERSPORTS_CCM_ENABLED=true/false`
- Transparent: User sees improved projections, not calibration mechanics

See [`hollersports/calibration/venue_coach_adjustments/README.md`](hollersports/calibration/venue_coach_adjustments/README.md) for detailed documentation.

## Quick Start

### Installation

```bash
# Clone repository
git clone https://github.com/scrimshawlife-ctrl/Hollersports.git
cd Hollersports

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v
```

### Basic Usage

```python
from abraxas.modules import backtest, GateConfig

# Configure and run backtest
cfg = GateConfig(min_signals_required=2)
df, report = backtest("your_legs.csv", cfg)

# View results
print(f"Hit rate improvement: {report['filtered_pts_lower_hit_rate'] - report['baseline_pts_lower_hit_rate']:+.1%}")

# Export detailed decisions
df.to_csv("legs_with_gate.csv", index=False)
```

See [`examples/run_backtest.py`](examples/run_backtest.py) for a complete example.

## Project Structure

```
Hollersports/
├── abraxas/                    # Abraxas Engine
│   ├── __init__.py
│   └── modules/                # ABX-Core Modules
│       ├── __init__.py
│       ├── scorer_under_gate.py
│       └── README.md
├── tests/                      # Comprehensive test suite
│   ├── __init__.py
│   └── test_scorer_under_gate.py
├── examples/                   # Usage examples
│   ├── legs_template.csv
│   └── run_backtest.py
├── requirements.txt
├── setup.py
└── README.md
```

## Data Format

Historical prop legs should be in CSV format with these columns:

**Required:**
- `date`, `player`, `team`, `opponent`
- `prop_type` (PTS, PRA, AST, etc.)
- `pick` (higher/lower)
- `line`, `result`

**Recommended:**
- `arena`, `home`, `spread`, `total`

See [`examples/legs_template.csv`](examples/legs_template.csv) for a template.

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test class
pytest tests/test_scorer_under_gate.py::TestGateLogic -v

# Check test coverage
pytest tests/ --cov=abraxas
```

All 33 tests pass with comprehensive coverage of:
- Provenance and determinism
- Gate logic with all signal combinations
- Feature engineering
- Edge cases and error handling
- Full backtest pipeline

## Provenance & Reproducibility

Every gate decision includes:
- **Provenance hash**: Deterministic fingerprint of config + signals
- **Config hash**: Version control for parameters
- **Gate reasons**: JSON dict of individual signal results

Same CSV + same config = **identical results**, byte-for-byte.

## Roadmap

**v0.2 (planned):**
- Additional ABX-Core modules (rebounds, assists, PRA gates)
- Live odds integration
- Enhanced teammate correlation tracking
- ROI-weighted backtests

**v0.3 (planned):**
- Web dashboard for interactive analysis
- Real-time bet slip validation
- Arena-specific suppression profiles
- Monte Carlo confidence intervals

## Contributing

This is a research/development project. For questions or issues:

1. Review module documentation in `abraxas/modules/README.md`
2. Check example usage in `examples/run_backtest.py`
3. Run test suite to verify functionality

## License

See [LICENSE](LICENSE) file for details.
