"""
Picker Engine for NHL SOG slate optimization.

Orchestrates all 5 components to build optimal slates.
"""

from typing import List, Dict, Optional
import numpy as np

from hollersports.nhl.types import (
    NHLGameRow,
    SOGProjection,
    SOGProp,
    Side,
    SlatePickResult,
    FeatureSet,
)
from hollersports.nhl.features import build_features
from hollersports.nhl.median_floor import compute_median_floor, assess_projection_quality
from hollersports.nhl.role_stability import check_role_stability
from hollersports.nhl.opponent_pressure import compute_opponent_modifier, apply_opponent_adjustment
from hollersports.nhl.monte_carlo import run_monte_carlo, estimate_confidence_from_distribution
from hollersports.nhl.anti_correlation import build_anti_correlated_slate, filter_slate_for_anti_correlation
from hollersports.nhl.provenance import compute_projection_provenance, compute_dataset_fingerprint, compute_config_hash


DEFAULT_CONFIG = {
    "min_confidence": 0.55,  # Minimum confidence to consider
    "min_p_hit": 0.58,  # Minimum Monte Carlo p_hit
    "seed": 1337,
}


def build_projection(
    player_id: str,
    game_id: str,
    line: float,
    side: Side,
    player_history: List[NHLGameRow],
    all_data: List[NHLGameRow],
    target_game: NHLGameRow,
    dataset_fingerprint: str,
    config: dict,
) -> Optional[SOGProjection]:
    """
    Build complete SOG projection for a single player-game-line.

    Integrates all 5 components of the spine.

    Args:
        player_id: Player identifier
        game_id: Game identifier
        line: Prop line
        side: HIGHER or LOWER
        player_history: Historical games for player
        all_data: Full dataset
        target_game: Game being projected
        dataset_fingerprint: Dataset hash for provenance
        config: Configuration dict

    Returns:
        SOGProjection or None if filtered out
    """
    # 1. Feature engineering
    features = build_features(player_id, game_id, player_history, all_data, target_game)

    # 2. Role stability filter (hard gate)
    role_result = check_role_stability(features, config)

    if not role_result.passed:
        # Hard reject
        return None

    # 3. Median-floor engine
    median, floor, sigma = compute_median_floor(features, config)

    # 4. Opponent pressure adjustment
    opponent_mod = compute_opponent_modifier(features, all_data, config)
    mu_adj = apply_opponent_adjustment(median, opponent_mod)

    # 5. Monte Carlo simulation
    mc_result = run_monte_carlo(mu_adj, sigma, line, side, config)

    # Check minimum p_hit threshold
    min_p_hit = config.get("min_p_hit", 0.58)
    if mc_result.p_hit < min_p_hit:
        return None

    # Compute overall confidence
    confidence = estimate_confidence_from_distribution(mc_result, median, floor, line, side)

    # Check minimum confidence threshold
    min_confidence = config.get("min_confidence", 0.55)
    if confidence < min_confidence:
        return None

    # Assess projection quality
    quality_score, reasons = assess_projection_quality(median, floor, line, side.value)

    # Add role stability info to reasons
    if role_result.toi_stable:
        reasons.append(f"TOI stable ({features.toi_season_median:.1f}min)")
    if role_result.pp_stable:
        reasons.append("PP usage stable")

    # Add opponent context
    if abs(opponent_mod) > 0.02:
        direction = "favorable" if opponent_mod > 0 else "tough"
        reasons.append(f"Opponent {direction} ({opponent_mod:+.1%})")

    # Flags
    flags = list(role_result.flags)
    if features.volatility_flag:
        flags.append("High volatility")

    # Compute provenance
    config_hash = compute_config_hash(config)
    provenance_hash = compute_projection_provenance(
        player_id, game_id, dataset_fingerprint, config_hash, config.get("seed", 1337)
    )

    # Get survivability score (placeholder - would come from AAL-core)
    survivability_score = 0.75  # TODO: Integrate with AAL-core normalizer

    return SOGProjection(
        player_id=player_id,
        player_name=target_game.player_name,
        game_id=game_id,
        mu=mu_adj,
        sigma=sigma,
        median=median,
        floor=floor,
        p_hit=mc_result.p_hit,
        confidence=confidence,
        line=line,
        side=side,
        reasons=reasons,
        flags=flags,
        provenance_hash=provenance_hash,
        role_score=role_result.role_score,
        opponent_modifier=opponent_mod,
        survivability_score=survivability_score,
    )


def pick_slate(
    slate_games: List[str],  # Game IDs in slate
    props: List[SOGProp],  # Props to evaluate
    all_data: List[NHLGameRow],
    config: dict = None,
) -> SlatePickResult:
    """
    Pick optimal legs from a slate of games.

    Args:
        slate_games: List of game IDs in slate
        props: List of SOGProp specifications to evaluate
        all_data: Full dataset
        config: Optional configuration

    Returns:
        SlatePickResult with ranked slates
    """
    if config is None:
        config = DEFAULT_CONFIG

    # Compute dataset fingerprint
    dataset_fingerprint = compute_dataset_fingerprint(all_data)

    # Build projections for all props
    projections = []

    for prop in props:
        # Find target game
        target_games = [
            g for g in all_data
            if g.player_id == prop.player_id and (prop.game_id is None or g.game_id == prop.game_id)
        ]

        if not target_games:
            continue

        target_game = target_games[0]  # Most recent or specified

        # Get player history (sorted by date, most recent first)
        player_history = [g for g in all_data if g.player_id == prop.player_id]
        player_history = sorted(player_history, key=lambda g: g.date, reverse=True)

        # Build projection
        projection = build_projection(
            player_id=prop.player_id,
            game_id=target_game.game_id,
            line=prop.line,
            side=prop.side,
            player_history=player_history,
            all_data=all_data,
            target_game=target_game,
            dataset_fingerprint=dataset_fingerprint,
            config=config,
        )

        if projection:
            projections.append(projection)

    total_candidates = len(projections)

    # Sort by confidence descending
    projections.sort(key=lambda p: p.confidence, reverse=True)

    # Ultra-safe 3-leg: top 3 by confidence
    ultra_safe_3leg = projections[:3]

    # Ultra-safe 5-leg: top 5 by confidence, filtered for anti-correlation
    filtered_5 = filter_slate_for_anti_correlation(projections[:10], all_data, max_same_team_overs=2)
    ultra_safe_5leg = filtered_5[:5]

    # Correlated 5-leg: allow same-team if requested
    correlated_5leg = projections[:5] if len(projections) >= 5 else projections

    # Balanced 5-leg: mix of high confidence and high p_hit
    # Sort by (confidence + p_hit) / 2
    balanced_candidates = sorted(projections, key=lambda p: (p.confidence + p.p_hit) / 2, reverse=True)
    balanced_5leg = balanced_candidates[:5]

    # Compute provenance
    config_hash = compute_config_hash(config)

    return SlatePickResult(
        ultra_safe_3leg=ultra_safe_3leg,
        ultra_safe_5leg=ultra_safe_5leg,
        correlated_5leg=correlated_5leg if len(correlated_5leg) == 5 else None,
        balanced_5leg=balanced_5leg if len(balanced_5leg) == 5 else None,
        total_candidates=total_candidates,
        filtered_candidates=len(projections),
        provenance_hash=config_hash,
    )
