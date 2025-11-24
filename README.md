# HollerSports

**A Sports Wagering assistant that uses Abraxas Symbolic intelligence engine and utilizes ABX-Core**

Built by Applied Alchemy Labs (AAL) under ABX-Core v1.2 principles: modular, deterministic, entropy-minimizing architecture with full provenance tracking.

## 🏗️ Architecture

HollerSports is a comprehensive sports betting props engine focused on NBA (with league-agnostic design for future expansion). The system processes player statistics through multiple enhancement layers to produce risk-scored prop recommendations and optimized parlays.

### Core Principles (ABX-Core v1.2)

- **Deterministic**: Same config + same data = same output
- **SEED Enforcement**: Full provenance tracking with seeds, config hashes, timestamps
- **Config-Driven**: No magic numbers; all tunables exposed in `config/settings.yaml`
- **Modular**: Small, composable jobs with clear boundaries
- **ERS Scheduler**: Event-reactive scheduling for job orchestration

### Data Flow Pipeline

```
Raw Data (API/CSV/DB)
  ↓
Base Projections
  ↓
VenueImpactEngine ──→ Apply arena-specific modifiers (pace, altitude, 3P environment)
  ↓
RolePriorityTagger ──→ Infer player roles (usage_hinge, glass_cleaner, etc.)
  ↓
GameScriptSimulator ──→ Model 3-5 game scripts (pace_up, shootout, grind, etc.)
  ↓
PropRiskScorer ──→ Unified risk profile (EV, volatility, fragility)
  ↓
ParlayBuilder v2 ──→ Conservative / Balanced / Aggressive parlays
  ↓
Bettor Console API ──→ Enriched JSON with venue tags, role tags, fragility indices
```

## 📦 Project Structure

```
Hollersports/
├── hollersports/              # Main package
│   ├── core/                  # ABX-Core compliance layer
│   │   ├── config.py         # Settings with SEED enforcement
│   │   ├── models.py         # Core data models
│   │   └── scheduler.py      # ERS job orchestration
│   ├── venue/                # VenueImpactEngine
│   ├── roles/                # RolePriorityTagger
│   ├── scripts/              # GameScriptSimulator
│   ├── props/                # PropRiskScorer
│   ├── parlays/              # ParlayBuilder v2
│   ├── data/                 # Data ingestion layer
│   └── api/                  # FastAPI (Bettor Console)
├── tests/
│   ├── unit/                 # Unit tests
│   ├── integration/          # Integration tests
│   └── fixtures/             # Golden test data
├── docs/                     # Documentation
├── config/                   # Configuration files
│   ├── settings.yaml         # Main settings
│   └── arenas.json           # Arena dataset (coming in Step 1)
├── pyproject.toml
├── requirements.txt
└── README.md
```

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/scrimshawlife-ctrl/Hollersports.git
cd Hollersports

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Or install in development mode
pip install -e ".[dev]"
```

### Configuration

Edit `config/settings.yaml` to customize behavior:

```yaml
# Core settings
seed: 42                    # Random seed for reproducibility
log_level: INFO

# Module toggles
venue:
  enabled: true
roles:
  enabled: true
scripts:
  enabled: true

# Parlay modes
parlays:
  conservative_max_fragility: 0.3
  balanced_max_fragility: 0.5
  aggressive_max_fragility: 0.75
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=hollersports --cov-report=html

# Run specific test categories
pytest -m unit
pytest -m integration
pytest -m golden
```

## 🎯 Module Overview

### VenueImpactEngine
Maintains dataset of NBA arenas with characteristics (altitude, pace modifiers, 3P environment, home-court effects). Applies venue-specific adjustments to base projections.

**Output**: Modified `PlayerProjection` with `venue_modifier` and `pace_modifier` tracked.

### RolePriorityTagger
Analyzes recent game logs and team context to infer player roles:
- `usage_hinge`: High-usage primary scorer
- `gravity_only`: Spacing/attention without the ball
- `glass_cleaner`: Rebounding specialist
- `connector`: Playmaking glue guy
- `bench_microwave`: Scoring punch off the bench
- `tunnel_scorer`: High-volume, low-assist scorer

**Output**: `RoleTag` with confidence score attached to each projection.

### GameScriptSimulator
Enumerates 3-5 plausible game scripts per matchup based on pace, ratings, spread, and injuries. Re-projects props under each script to compute **Fragility Index**: how much the pick depends on a narrow script.

**Scripts**: `pace_up`, `pace_down`, `shootout`, `grind`, `blowout`, `balanced`

**Output**: List of `ScriptProjection` objects with probabilities and hit rates per script.

### PropRiskScorer
Combines venue effects, role tags, and script simulations into a unified risk profile:

- **value_score**: Expected edge vs book line
- **volatility_score**: Range of outcomes
- **fragility_index**: Script dependence (0-1, higher = more fragile)
- **recommended_side**: `"higher"`, `"lower"`, or `"avoid"`

### ParlayBuilder v2
Constructs parlays in three risk profiles:

1. **Conservative**: Low fragility (≤0.3), high confidence (≥5% EV)
2. **Balanced**: Medium fragility (≤0.5), moderate EV (≥3%)
3. **Aggressive**: Higher risk (≤0.75), lower EV threshold (≥1%)

Enforces diversification: max 2 legs per game, script robustness checks.

### Bettor Console API
FastAPI endpoints exposing projections, prop analysis, and parlay recommendations with enriched metadata:
- Arena tags (e.g., `@DEN (Altitude+, Pace+)`)
- Role tags (e.g., `Jokic: usage_hinge`)
- Script robustness (e.g., `3/4 scripts green`)
- Fragility indices and risk scores

## 📊 Configuration Reference

All tunables are in `config/settings.yaml`:

| Setting | Default | Description |
|---------|---------|-------------|
| `seed` | 42 | Global random seed |
| `venue.enabled` | true | Enable venue modifiers |
| `roles.usage_hinge_threshold` | 28.0 | USG% for usage_hinge tag |
| `scripts.num_scripts_per_matchup` | 5 | Scripts to simulate |
| `scripts.fragility_high_threshold` | 0.6 | High fragility cutoff |
| `prop_risk.min_ev_threshold` | 0.03 | Min EV to consider (3%) |
| `parlays.conservative_max_fragility` | 0.3 | Conservative mode cap |
| `parlays.max_legs_same_game` | 2 | Max legs from one game |

## 🧪 Testing Philosophy

- **Unit tests**: Each module tested in isolation with synthetic data
- **Integration tests**: Full pipeline tests with realistic scenarios
- **Golden tests**: Historical slate data to validate that bad legs are flagged as high-fragility

Principle: Bad picks from the past should score high fragility or `"avoid"` with the new system.

## 📝 Development Status

### ✅ Completed
- [x] Step 0: Foundation (Project structure, core models, ABX-Core compliance)

### 🚧 In Progress
- [ ] Step 1: VenueImpactEngine
- [ ] Step 2: RolePriorityTagger
- [ ] Step 3: GameScriptSimulator
- [ ] Step 4: PropRiskScorer
- [ ] Step 5: ParlayBuilder v2
- [ ] Step 6: Bettor Console API
- [ ] Step 7: Tests & Validation
- [ ] Step 8: Documentation

## 🤝 Contributing

This is a private project under Applied Alchemy Labs. For questions or issues, contact the development team.

## 📄 License

MIT License - see LICENSE file for details.

## 🔗 Links

- **Applied Alchemy Labs**: [appliedalchemy.io](https://appliedalchemy.io)
- **ABX-Core Documentation**: [Internal wiki]
- **Issue Tracker**: [GitHub Issues](https://github.com/scrimshawlife-ctrl/Hollersports/issues)

---

Built with ABX-Core v1.2 | Powered by Abraxas Symbolic Intelligence
