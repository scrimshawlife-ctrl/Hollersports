"""
ParlayBuilder v2 - Multi-tier parlay construction.

Responsibilities:
- Build parlays in Conservative, Balanced, and Aggressive modes
- Apply fragility filtering based on mode
- Enforce diversification rules
- Calculate aggregate risk metrics
- Generate parlay recommendations
"""

from typing import Optional

from hollersports.core.config import Settings, get_settings
from hollersports.parlays.models import Parlay, ParlayLeg, ParlayMode
from hollersports.props.models import PropRiskProfile


class ParlayBuilder:
    """
    Builder for constructing optimized parlays from prop risk profiles.

    Three modes:
    - Conservative: Low fragility (≤0.3), high confidence (≥5% EV)
    - Balanced: Medium fragility (≤0.5), moderate EV (≥3%)
    - Aggressive: Higher risk (≤0.75), lower EV threshold (≥1%)

    Enforces:
    - Diversification (max 2 legs per game)
    - Script robustness (filters fragile props based on mode)
    - Minimum/maximum leg counts
    """

    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize ParlayBuilder.

        Args:
            settings: Settings instance (will load default if not provided)
        """
        self.settings = settings or get_settings()

    def build_parlay(
        self,
        candidates: list[PropRiskProfile],
        mode: ParlayMode,
        parlay_id: str,
        num_legs: Optional[int] = None,
    ) -> Optional[Parlay]:
        """
        Build a parlay from candidate props.

        Args:
            candidates: List of PropRiskProfile objects to choose from
            mode: Parlay construction mode
            parlay_id: Unique identifier for this parlay
            num_legs: Optional target number of legs (will use best available if not specified)

        Returns:
            Parlay object, or None if insufficient valid candidates
        """
        # Filter candidates based on mode
        filtered = self._filter_candidates_by_mode(candidates, mode)

        if not filtered:
            return None

        # Select legs with diversification
        selected = self._select_legs_with_diversification(
            filtered, mode, target_legs=num_legs
        )

        if len(selected) < self.settings.parlays.min_legs:
            return None

        # Create parlay legs
        legs = [self._create_parlay_leg(prop) for prop in selected]

        # Calculate aggregate metrics
        combined_odds = self._calculate_combined_odds(legs)
        combined_implied_prob = self._calculate_combined_implied_prob(legs)
        expected_hit_prob = self._calculate_expected_hit_prob(selected)

        avg_fragility = sum(p.fragility_index for p in selected) / len(selected)
        avg_confidence = sum(p.confidence for p in selected) / len(selected)
        avg_value_score = sum(p.value_score for p in selected) / len(selected)

        # Diversification metrics
        num_unique_games = len(set(self._extract_matchup_id(p) for p in selected))
        num_unique_stats = len(set(p.stat for p in selected))

        # Generate tags
        tags = self._generate_parlay_tags(selected, mode)

        return Parlay(
            parlay_id=parlay_id,
            mode=mode,
            legs=legs,
            combined_odds=combined_odds,
            combined_implied_prob=combined_implied_prob,
            expected_hit_prob=expected_hit_prob,
            avg_fragility=avg_fragility,
            avg_confidence=avg_confidence,
            avg_value_score=avg_value_score,
            num_unique_games=num_unique_games,
            num_unique_stats=num_unique_stats,
            tags=tags,
        )

    def build_all_modes(
        self, candidates: list[PropRiskProfile], base_id: str = "parlay"
    ) -> dict[ParlayMode, Optional[Parlay]]:
        """
        Build parlays for all three modes.

        Args:
            candidates: List of PropRiskProfile objects
            base_id: Base ID for parlay naming

        Returns:
            Dict mapping mode to Parlay (or None if not possible)
        """
        return {
            ParlayMode.CONSERVATIVE: self.build_parlay(
                candidates, ParlayMode.CONSERVATIVE, f"{base_id}_conservative"
            ),
            ParlayMode.BALANCED: self.build_parlay(
                candidates, ParlayMode.BALANCED, f"{base_id}_balanced"
            ),
            ParlayMode.AGGRESSIVE: self.build_parlay(
                candidates, ParlayMode.AGGRESSIVE, f"{base_id}_aggressive"
            ),
        }

    def _filter_candidates_by_mode(
        self, candidates: list[PropRiskProfile], mode: ParlayMode
    ) -> list[PropRiskProfile]:
        """
        Filter candidates based on mode thresholds.

        Args:
            candidates: All candidate props
            mode: Construction mode

        Returns:
            Filtered list meeting mode criteria
        """
        # Get thresholds for this mode
        if mode == ParlayMode.CONSERVATIVE:
            max_fragility = self.settings.parlays.conservative_max_fragility
            min_ev = self.settings.parlays.conservative_min_ev
        elif mode == ParlayMode.BALANCED:
            max_fragility = self.settings.parlays.balanced_max_fragility
            min_ev = self.settings.parlays.balanced_min_ev
        else:  # AGGRESSIVE
            max_fragility = self.settings.parlays.aggressive_max_fragility
            min_ev = self.settings.parlays.aggressive_min_ev

        filtered = []
        for prop in candidates:
            # Must be recommended (not "avoid")
            if not prop.is_recommended():
                continue

            # Check fragility threshold
            if prop.fragility_index > max_fragility:
                continue

            # Check EV threshold
            if prop.value_score < min_ev:
                continue

            filtered.append(prop)

        return filtered

    def _select_legs_with_diversification(
        self,
        candidates: list[PropRiskProfile],
        mode: ParlayMode,
        target_legs: Optional[int] = None,
    ) -> list[PropRiskProfile]:
        """
        Select legs with diversification constraints.

        Args:
            candidates: Filtered candidates
            mode: Construction mode
            target_legs: Optional target number of legs

        Returns:
            Selected props (diversified)
        """
        if not target_legs:
            # Use mode-appropriate default
            if mode == ParlayMode.CONSERVATIVE:
                target_legs = 3
            elif mode == ParlayMode.BALANCED:
                target_legs = 4
            else:
                target_legs = 5

        # Cap at max_legs setting
        target_legs = min(target_legs, self.settings.parlays.max_legs)

        # Sort by value score (descending)
        sorted_candidates = sorted(candidates, key=lambda p: p.value_score, reverse=True)

        selected: list[PropRiskProfile] = []
        matchup_counts: dict[str, int] = {}

        for prop in sorted_candidates:
            if len(selected) >= target_legs:
                break

            matchup_id = self._extract_matchup_id(prop)

            # Check diversification constraint
            current_count = matchup_counts.get(matchup_id, 0)
            if current_count >= self.settings.parlays.max_legs_same_game:
                continue

            # Add to selected
            selected.append(prop)
            matchup_counts[matchup_id] = current_count + 1

        return selected

    def _create_parlay_leg(self, prop: PropRiskProfile) -> ParlayLeg:
        """
        Create a ParlayLeg from PropRiskProfile.

        Args:
            prop: Prop risk profile

        Returns:
            ParlayLeg with odds
        """
        # Default to -110 odds (standard)
        # In production, this would come from the actual sportsbook
        odds = -110

        return ParlayLeg(prop_risk_profile=prop, odds=odds)

    def _calculate_combined_odds(self, legs: list[ParlayLeg]) -> float:
        """
        Calculate combined decimal odds for parlay.

        Args:
            legs: Parlay legs

        Returns:
            Combined decimal odds
        """
        combined = 1.0
        for leg in legs:
            combined *= leg.decimal_odds
        return combined

    def _calculate_combined_implied_prob(self, legs: list[ParlayLeg]) -> float:
        """
        Calculate combined implied probability from book.

        Args:
            legs: Parlay legs

        Returns:
            Combined implied probability
        """
        prob = 1.0
        for leg in legs:
            prob *= leg.implied_prob
        return prob

    def _calculate_expected_hit_prob(self, props: list[PropRiskProfile]) -> float:
        """
        Calculate expected probability all props hit.

        Uses our estimated probabilities, not book's.

        Args:
            props: Selected props

        Returns:
            Combined probability
        """
        prob = 1.0
        for prop in props:
            prob *= prop.implied_prob_over
        return prob

    def _extract_matchup_id(self, prop: PropRiskProfile) -> str:
        """
        Extract matchup ID from prop for diversification.

        Args:
            prop: Prop risk profile

        Returns:
            Matchup identifier (e.g., "PHX_vs_LAL")
        """
        # In production, this would be in the prop metadata
        # For now, use a placeholder based on player
        return f"matchup_{prop.player_id[:3]}"

    def _generate_parlay_tags(
        self, props: list[PropRiskProfile], mode: ParlayMode
    ) -> list[str]:
        """
        Generate parlay-level tags.

        Args:
            props: Selected props
            mode: Construction mode

        Returns:
            List of tags
        """
        tags = []

        # Add mode tag
        tags.append(f"mode_{mode.value}")

        # Check if all props are robust
        if all(p.fragility_index < 0.3 for p in props):
            tags.append("all_robust")

        # Check if high confidence
        avg_conf = sum(p.confidence for p in props) / len(props)
        if avg_conf > 0.75:
            tags.append("high_confidence")

        # Check diversification
        unique_stats = len(set(p.stat for p in props))
        if unique_stats >= len(props) - 1:
            tags.append("well_diversified")

        # Check value
        avg_value = sum(p.value_score for p in props) / len(props)
        if avg_value > 0.08:
            tags.append("strong_value")

        return tags
