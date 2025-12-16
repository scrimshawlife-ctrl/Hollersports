"""
NFL SCMF Picker - Main orchestration module.

Coordinates 5-part spine to build ultra-safe slates.
"""

from typing import List, Optional
from hollersports.nfl.types import (
    NFLGameRow,
    PropLeg,
    Projection,
    SlatePickResult,
    Market,
    Side,
    EVENT_MARKETS,
)
from hollersports.nfl import features, script_tree, median_floor, role_stability, opponent_pressure, monte_carlo, provenance, anti_correlation


def pick_slate(
    slate_games: List[str],
    props: List[PropLeg],
    all_data: List[NFLGameRow],
    config: dict,
) -> SlatePickResult:
    """
    Pick optimal slate from available props.

    5-part spine:
    1. Script-Conditioned Median-Floor
    2. Role Stability Filter (position-specific)
    3. Opponent Pressure Model (bounded)
    4. Anti-Correlation Architecture (position-aware)
    5. Monte Carlo Simulation (150k runs, market-specific)

    Args:
        slate_games: List of game IDs in slate
        props: List of prop bets to evaluate
        all_data: Full historical dataset
        config: Configuration dict

    Returns:
        SlatePickResult with ultra-safe 3-leg and 5-leg slates
    """
    dataset_fingerprint = provenance.compute_dataset_fingerprint(all_data)

    # Build projections for all props
    candidates = []

    for prop in props:
        # Only process props in slate games
        if prop.game_id not in slate_games:
            continue

        # Ultra-safe mode: forbid event markets (TDs)
        if config.get("ultra_safe_mode", True):
            if prop.market in EVENT_MARKETS:
                continue

        # Build projection
        proj = build_projection(
            player_id=prop.player_id,
            game_id=prop.game_id,
            line=prop.line,
            side=prop.side,
            market=prop.market,
            player_history=_get_player_history(prop.player_id, all_data, prop.game_id),
            all_data=all_data,
            dataset_fingerprint=dataset_fingerprint,
            config=config,
        )

        if proj is not None:
            candidates.append(proj)

    # Filter by thresholds
    min_confidence = config.get("min_confidence", 0.65)
    min_p_hit = config.get("min_p_hit", 0.60)

    filtered = [
        c for c in candidates
        if c.confidence >= min_confidence and c.p_hit >= min_p_hit
    ]

    # Build anti-correlated slates
    ultra_safe_3leg = anti_correlation.build_anti_correlated_slate(
        filtered, all_data, target_size=3
    )

    ultra_safe_5leg = anti_correlation.build_anti_correlated_slate(
        filtered, all_data, target_size=5
    )

    return SlatePickResult(
        ultra_safe_3leg=ultra_safe_3leg,
        ultra_safe_5leg=ultra_safe_5leg,
        total_candidates=len(candidates),
        filtered_candidates=len(filtered),
        provenance_hash=dataset_fingerprint,
    )


def build_projection(
    player_id: str,
    game_id: str,
    line: float,
    side: Side,
    market: Market,
    player_history: List[NFLGameRow],
    all_data: List[NFLGameRow],
    dataset_fingerprint: str,
    config: dict,
) -> Optional[Projection]:
    """
    Build full projection for a prop.

    Returns:
        Projection or None if filtered out
    """
    if len(player_history) < 3:
        return None  # Insufficient history

    # Get target game
    target_game = _get_target_game(player_id, game_id, all_data)
    if target_game is None:
        return None

    # 1. Build features
    feat = features.build_features(player_id, game_id, player_history, all_data)
    if feat is None:
        return None

    # 2. Check role stability (position-specific gates)
    role_result = role_stability.check_role_stability(feat, market, config)
    if not role_result.passed:
        return None  # Failed role gate

    # 3. Compute script priors from vegas
    script_priors = script_tree.compute_script_priors(
        target_game.vegas_spread,
        target_game.vegas_total,
    )

    # 4. Compute median, floor, sigma (script-conditioned)
    med, flr, sig, script_mus = median_floor.compute_median_floor(
        feat, market, script_priors, target_game, config
    )

    if med == 0:
        return None  # No projection possible

    # 5. Apply opponent adjustments (bounded)
    med_adjusted = opponent_pressure.apply_opponent_adjustments(
        med, market, target_game, config
    )

    # 6. Monte Carlo simulation (150k runs, market-specific)
    mc_result = monte_carlo.run_monte_carlo(
        mu=med_adjusted,
        sigma=sig,
        line=line,
        side=side,
        market=market,
        config=config,
    )

    # 7. Estimate confidence
    confidence = monte_carlo.estimate_confidence_from_distribution(
        mc_result, med_adjusted, flr, line, side
    )

    # 8. Build reasons and flags
    reasons = _build_reasons(role_result, script_priors, mc_result, market)
    flags = role_result.flags.copy() if role_result.flags else []

    # 9. Compute provenance hash
    prov_hash = provenance.compute_provenance_hash(
        player_id=player_id,
        game_id=game_id,
        market=market.value,
        line=line,
        side=side.value,
        script_priors={k.value: v for k, v in script_priors.items()},
        config=config,
        dataset_fingerprint=dataset_fingerprint,
    )

    # 10. Build Projection
    proj = Projection(
        player_id=player_id,
        player_name=target_game.player_name,
        position=target_game.position,
        game_id=game_id,
        market=market,
        mu=med_adjusted,
        sigma=sig,
        median=med_adjusted,
        floor=flr,
        script_mus=script_mus,
        script_priors={k.value: v for k, v in script_priors.items()},
        p_hit=mc_result.p_hit,
        confidence=confidence,
        line=line,
        side=side,
        reasons=reasons,
        flags=flags,
        provenance_hash=prov_hash,
        role_score=role_result.role_score,
        opponent_modifier=opponent_pressure.compute_opponent_modifier(market, target_game, config),
        survivability_score=_compute_survivability(market),
    )

    return proj


def _get_player_history(
    player_id: str,
    all_data: List[NFLGameRow],
    target_game_id: str,
) -> List[NFLGameRow]:
    """Get player history before target game."""
    history = [
        row for row in all_data
        if row.player_id == player_id and row.game_id != target_game_id
    ]
    # Sort by date
    history.sort(key=lambda r: r.date)
    return history


def _get_target_game(
    player_id: str,
    game_id: str,
    all_data: List[NFLGameRow],
) -> Optional[NFLGameRow]:
    """Get target game row."""
    for row in all_data:
        if row.player_id == player_id and row.game_id == game_id:
            return row
    return None


def _build_reasons(
    role_result,
    script_priors,
    mc_result,
    market: Market,
) -> List[str]:
    """Build explanation reasons."""
    reasons = []

    # Role score
    reasons.append(f"Role score: {role_result.role_score:.2f}")

    # Script state
    dominant_script = max(script_priors.items(), key=lambda x: x[1])
    reasons.append(f"Dominant script: {dominant_script[0].value} ({dominant_script[1]:.1%})")

    # Monte Carlo
    reasons.append(f"P(hit): {mc_result.p_hit:.1%} (150k sims)")

    # Floor
    reasons.append(f"Floor: {mc_result.p25:.1f} (p25)")

    return reasons


def _compute_survivability(market: Market) -> float:
    """
    Compute market survivability score.

    High survivability markets (volume) score higher.
    """
    from hollersports.nfl.types import HIGH_SURVIVABILITY_MARKETS, MEDIUM_SURVIVABILITY_MARKETS

    if market in HIGH_SURVIVABILITY_MARKETS:
        return 1.0
    elif market in MEDIUM_SURVIVABILITY_MARKETS:
        return 0.75
    elif market in EVENT_MARKETS:
        return 0.25  # Low survivability (TDs)
    else:
        return 0.50  # Default
