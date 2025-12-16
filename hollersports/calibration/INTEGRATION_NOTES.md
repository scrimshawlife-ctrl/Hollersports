# CCM Integration Guide

**How to integrate Contextual Correction Maps into your existing projection pipeline**

## TL;DR

```python
# 1. At application startup (once)
from hollersports.calibration.apply_adjustments import initialize_ccm
initialize_ccm()

# 2. In your projection pipeline (for each prop)
from hollersports.calibration.apply_adjustments import apply_adjustment
from hollersports.calibration.venue_coach_adjustments.models import PropMarket, GameContext, PropRecord

# Your existing code generates raw projection
raw_projection = your_model.predict(player, matchup, ...)

# Build context and record objects
context = GameContext(
    venue_id=game.venue_id,
    is_home=game.is_home_for_player_team,
    team_id=player.team_id,
    opp_id=game.opponent_id,
    coach_id=player.team_coach_id,  # Optional but recommended
    travel_b2b=game.is_back_to_back,  # Optional
    timezone_delta=game.timezone_diff,  # Optional
    rest_days=game.rest_days,  # Optional
)

record = PropRecord(
    player_id=player.id,
    game_id=game.id,
    market=PropMarket.PTS,  # or PRA, REB, AST, etc.
    line=bookmaker_line,
    actual=0.0,  # Not used for runtime prediction
    side=PropSide.HIGHER,  # Not critical for adjustment
    timestamp=game.datetime.isoformat(),
    team_id=player.team_id,
    opp_id=game.opponent_id,
    venue_id=game.venue_id,
)

# Apply CCM adjustment
adjusted_projection = apply_adjustment(
    projection=raw_projection,
    market=PropMarket.PTS,
    context=context,
    record=record,
)

# Use adjusted projection downstream
pick_higher = adjusted_projection > bookmaker_line
```

## Integration Points

### Option A: Wrapper Function (Recommended)

Create a wrapper around your existing prediction function:

```python
# projection_engine.py

from hollersports.calibration.apply_adjustments import apply_adjustment
from hollersports.calibration.venue_coach_adjustments.models import PropMarket, GameContext, PropRecord, PropSide

def predict_prop_with_calibration(player, game, market_str, line):
    """
    Predict prop outcome with CCM calibration applied.

    Args:
        player: Player object with id, team_id
        game: Game object with venue_id, opponent_id, datetime, etc.
        market_str: Market name ('PTS', 'REB', etc.)
        line: Bookmaker line

    Returns:
        Tuple of (adjusted_projection, raw_projection, confidence)
    """
    # 1. Generate raw projection (your existing model)
    raw_projection = your_existing_model.predict(player, game, market_str)

    # 2. Build CCM context
    context = GameContext(
        venue_id=game.venue_id,
        is_home=(player.team_id == game.home_team_id),
        team_id=player.team_id,
        opp_id=game.away_team_id if player.team_id == game.home_team_id else game.home_team_id,
        coach_id=player.team.coach_id if hasattr(player.team, 'coach_id') else None,
        travel_b2b=game.is_back_to_back if hasattr(game, 'is_back_to_back') else None,
        timezone_delta=game.timezone_delta if hasattr(game, 'timezone_delta') else None,
        rest_days=game.rest_days if hasattr(game, 'rest_days') else None,
    )

    # 3. Build PropRecord for feature extraction
    record = PropRecord(
        player_id=player.id,
        game_id=game.id,
        market=PropMarket(market_str),
        line=line,
        actual=0.0,  # Placeholder
        side=PropSide.HIGHER,  # Placeholder
        timestamp=game.datetime.isoformat(),
        team_id=player.team_id,
        opp_id=context.opp_id,
        venue_id=game.venue_id,
    )

    # 4. Apply CCM adjustment
    adjusted_projection = apply_adjustment(
        projection=raw_projection,
        market=PropMarket(market_str),
        context=context,
        record=record,
    )

    # 5. Return both for transparency
    return adjusted_projection, raw_projection
```

Then update your calling code:

```python
# Before:
projection = predict_prop(player, game, 'PTS', line)

# After:
adjusted, raw = predict_prop_with_calibration(player, game, 'PTS', line)
projection = adjusted  # Use adjusted projection
```

### Option B: In-Place Modification

Modify your existing prediction function to apply CCM before returning:

```python
# projection_engine.py

def predict_prop(player, game, market, line):
    # ... your existing prediction logic ...

    projection = compute_projection(...)

    # NEW: Apply CCM calibration
    if CCM_ENABLED:  # Check environment variable
        from hollersports.calibration.apply_adjustments import apply_adjustment
        from hollersports.calibration.venue_coach_adjustments.models import ...

        context = build_game_context(game, player)
        record = build_prop_record(player, game, market, line)

        projection = apply_adjustment(projection, market, context, record)

    return projection
```

### Option C: Pipeline Layer

Add CCM as an explicit layer in a multi-stage pipeline:

```python
# pipeline.py

class PropPredictionPipeline:
    def __init__(self):
        self.base_model = YourBaseModel()
        self.calibration_layer = CCMCalibrationLayer()

    def predict(self, player, game, market, line):
        # Stage 1: Base model
        raw = self.base_model.predict(player, game, market)

        # Stage 2: Calibration
        adjusted = self.calibration_layer.apply(raw, player, game, market, line)

        # Stage 3: Additional post-processing (if any)
        final = self.post_process(adjusted)

        return final


class CCMCalibrationLayer:
    def __init__(self):
        from hollersports.calibration.apply_adjustments import initialize_ccm
        initialize_ccm()

    def apply(self, projection, player, game, market, line):
        # Build context and apply
        context = self._build_context(player, game)
        record = self._build_record(player, game, market, line)

        from hollersports.calibration.apply_adjustments import apply_adjustment
        from hollersports.calibration.venue_coach_adjustments.models import PropMarket

        return apply_adjustment(projection, PropMarket(market), context, record)
```

## Startup Initialization

### Web Application (Flask/FastAPI)

```python
# app.py

from flask import Flask
from hollersports.calibration.apply_adjustments import initialize_ccm, get_ccm_status

app = Flask(__name__)

@app.before_first_request
def startup():
    """Initialize CCM on application startup."""
    initialize_ccm()
    status = get_ccm_status()
    app.logger.info(f"CCM initialized: {status}")

# ... your routes ...
```

### Script/Batch Job

```python
# daily_predictions.py

from hollersports.calibration.apply_adjustments import initialize_ccm

def main():
    # Initialize CCM once at script start
    initialize_ccm()

    # Process all games
    for game in today_games:
        for player in game.players:
            projection = predict_with_ccm(player, game, ...)
            save_prediction(projection)

if __name__ == "__main__":
    main()
```

### Jupyter Notebook

```python
# notebook.ipynb

from hollersports.calibration.apply_adjustments import initialize_ccm

# Run once per session
initialize_ccm()

# Now all predictions will use CCM
for game in games:
    ...
```

## Configuration

### Environment Variables

```bash
# Enable CCM (default)
export HOLLERSPORTS_CCM_ENABLED=true

# Disable CCM (use raw projections only)
export HOLLERSPORTS_CCM_ENABLED=false
```

### Custom CCM Path

```python
from pathlib import Path
from hollersports.calibration.apply_adjustments import initialize_ccm

# Load CCM from custom path
initialize_ccm(Path("/path/to/custom/correction_maps.json"))
```

## Monitoring

### Add Logging

```python
import logging
from hollersports.calibration.apply_adjustments import apply_adjustment

logger = logging.getLogger(__name__)

def predict_with_logging(player, game, market, line):
    raw = base_predict(player, game, market)

    context = build_context(player, game)
    record = build_record(player, game, market, line)

    adjusted = apply_adjustment(raw, market, context, record)

    delta = adjusted - raw
    if abs(delta) > 0.5:  # Log significant adjustments
        logger.info(
            f"CCM adjustment: {player.name} {market} "
            f"raw={raw:.1f} → adjusted={adjusted:.1f} (Δ{delta:+.1f}) "
            f"venue={game.venue_id}"
        )

    return adjusted
```

### Metrics Collection

```python
from dataclasses import dataclass
from collections import defaultdict

@dataclass
class CCMMetrics:
    """Track CCM usage metrics."""
    total_predictions: int = 0
    ccm_applied: int = 0
    avg_delta: float = 0.0
    max_delta: float = 0.0

metrics = CCMMetrics()

def predict_with_metrics(player, game, market, line):
    metrics.total_predictions += 1

    raw = base_predict(player, game, market)
    adjusted = apply_calibration(raw, player, game, market, line)

    delta = adjusted - raw
    if delta != 0:
        metrics.ccm_applied += 1
        metrics.avg_delta = (metrics.avg_delta * (metrics.ccm_applied - 1) + delta) / metrics.ccm_applied
        metrics.max_delta = max(metrics.max_delta, abs(delta))

    return adjusted

# Report metrics periodically
def report_metrics():
    pct_applied = 100 * metrics.ccm_applied / metrics.total_predictions if metrics.total_predictions > 0 else 0
    print(f"CCM applied to {pct_applied:.1f}% of predictions")
    print(f"Average delta: {metrics.avg_delta:+.2f}")
    print(f"Max delta: {metrics.max_delta:.2f}")
```

## Testing Integration

### Unit Test with Mock CCM

```python
# test_integration.py

import pytest
from unittest.mock import patch, MagicMock

def test_prediction_pipeline_with_ccm():
    """Test that CCM is called during prediction."""

    # Mock CCM
    with patch('hollersports.calibration.apply_adjustments.apply_adjustment') as mock_apply:
        mock_apply.return_value = 24.0  # Adjusted projection

        result = predict_prop_with_calibration(
            player=mock_player,
            game=mock_game,
            market_str='PTS',
            line=25.5,
        )

        # Verify CCM was called
        assert mock_apply.called
        adjusted, raw = result
        assert adjusted == 24.0
```

### Integration Test with Real CCM

```python
def test_prediction_with_real_ccm():
    """Test prediction with actual CCM artifact."""
    from hollersports.calibration.apply_adjustments import initialize_ccm
    from pathlib import Path

    # Load test CCM
    test_ccm_path = Path("tests/fixtures/test_correction_maps.json")
    initialize_ccm(test_ccm_path)

    # Run prediction
    adjusted, raw = predict_prop_with_calibration(
        player=test_player,
        game=test_game,
        market_str='PTS',
        line=25.5,
    )

    # Verify adjustment applied
    assert adjusted != raw or not CCM_ENABLED
```

## Rollback Plan

If CCM causes issues in production:

### Immediate Rollback (No Code Change)

```bash
# Disable CCM via environment variable
export HOLLERSPORTS_CCM_ENABLED=false

# Restart application
systemctl restart hollersports-api
```

### Code Rollback

```python
# Revert to raw projections
def predict_prop(player, game, market, line):
    projection = base_model.predict(...)
    # REMOVED: projection = apply_adjustment(...)
    return projection
```

### Gradual Rollout

Use feature flag for gradual rollout:

```python
from your_feature_flag_service import is_enabled

def predict_prop(player, game, market, line):
    raw = base_predict(...)

    if is_enabled('ccm_calibration', user_id=player.user_id):
        return apply_calibration(raw, ...)
    else:
        return raw
```

## Next Steps

1. **Generate CCM**: Run backtest on historical data
2. **Deploy artifact**: Copy `correction_maps.json` to production
3. **Initialize at startup**: Add `initialize_ccm()` call
4. **Update prediction logic**: Apply `apply_adjustment()`
5. **Monitor**: Log adjustments and track metrics
6. **Iterate**: Re-train CCM monthly with fresh data

## Support

Questions? Check:
- [`venue_coach_adjustments/README.md`](venue_coach_adjustments/README.md) - Full CCM documentation
- [`schema.yaml`](venue_coach_adjustments/schema.yaml) - Data schema reference
- `tests/test_*.py` - Test examples
