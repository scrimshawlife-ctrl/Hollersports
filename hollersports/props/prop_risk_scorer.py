"""
PropRiskScorer - Unified risk scoring for player props.

Responsibilities:
- Integrate venue, role, and script analysis
- Calculate value score (EV vs book line)
- Compute volatility score (outcome variance)
- Extract fragility index from script analysis
- Generate recommendation with confidence
"""

from typing import Literal, Optional

from hollersports.core.config import Settings, get_settings
from hollersports.core.models import PlayerProjection, PropLine, PropSide, StatCategory
from hollersports.props.models import PropRiskProfile
from hollersports.roles.models import RoleTag
from hollersports.scripts.models import FragilityAnalysis
from hollersports.venue.models import VenueProfile


class PropRiskScorer:
    """
    Scorer for comprehensive prop risk analysis.

    Combines:
    - VenueProfile (pace, altitude, 3P environment)
    - RoleTag (player role context)
    - FragilityAnalysis (script dependence)

    Into a unified PropRiskProfile with:
    - value_score: EV vs book line
    - volatility_score: outcome variance
    - fragility_index: script dependence
    - recommended_side: higher/lower/avoid
    """

    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize PropRiskScorer.

        Args:
            settings: Settings instance (will load default if not provided)
        """
        self.settings = settings or get_settings()

    def score_prop(
        self,
        projection: PlayerProjection,
        prop_line: PropLine,
        venue_profile: Optional[VenueProfile] = None,
        role_tag: Optional[RoleTag] = None,
        fragility_analysis: Optional[FragilityAnalysis] = None,
    ) -> PropRiskProfile:
        """
        Generate comprehensive risk profile for a prop.

        Args:
            projection: PlayerProjection (venue-adjusted)
            prop_line: Betting line to evaluate
            venue_profile: Optional venue context
            role_tag: Optional role context
            fragility_analysis: Optional script fragility analysis

        Returns:
            PropRiskProfile with all risk metrics
        """
        # Get projected value for this stat
        proj_value = projection.get_stat_value(prop_line.stat)
        proj_std = projection.get_stat_std(prop_line.stat)

        # If we have fragility analysis, use script-weighted values
        if fragility_analysis:
            projected_value = fragility_analysis.weighted_mean
            proj_std = max(proj_std, fragility_analysis.weighted_std)
            fragility_index = fragility_analysis.fragility_index

            # Calculate implied probability from script analysis
            implied_prob_over = self._calculate_script_weighted_prob(
                fragility_analysis, prop_line.line
            )
        else:
            projected_value = proj_value
            fragility_index = 0.5  # Neutral fragility if no script analysis

            # Calculate implied probability using normal distribution
            implied_prob_over = self._calculate_normal_prob(
                projected_value, proj_std, prop_line.line
            )

        # Calculate value score (EV vs book)
        value_score = self._calculate_value_score(
            implied_prob_over, prop_line.implied_prob(PropSide.OVER)
        )

        # Calculate volatility score
        volatility_score = self._calculate_volatility_score(
            projected_value, proj_std, role_tag
        )

        # Generate recommendation
        recommended_side, confidence = self._generate_recommendation(
            value_score, volatility_score, fragility_index, implied_prob_over, prop_line
        )

        # Calculate expected value in units
        expected_value = projected_value - prop_line.line

        # Generate risk tags
        risk_tags = self._generate_risk_tags(
            value_score, volatility_score, fragility_index, role_tag
        )

        # Extract venue tags
        venue_tags = venue_profile.tags if venue_profile else []

        return PropRiskProfile(
            player_id=projection.player_id,
            player_name=projection.player_name,
            stat=prop_line.stat.value,
            line=prop_line.line,
            value_score=value_score,
            volatility_score=volatility_score,
            fragility_index=fragility_index,
            recommended_side=recommended_side,
            confidence=confidence,
            venue_profile=venue_profile,
            role_tag=role_tag,
            fragility_analysis=fragility_analysis,
            projected_value=projected_value,
            implied_prob_over=implied_prob_over,
            expected_value=expected_value,
            risk_tags=risk_tags,
            venue_tags=venue_tags,
        )

    def _calculate_value_score(self, true_prob: float, implied_prob: float) -> float:
        """
        Calculate value score (edge vs book).

        Args:
            true_prob: Our estimated probability
            implied_prob: Book's implied probability

        Returns:
            Value score (-1 to 1, positive = edge)
        """
        # Edge = true_prob - implied_prob
        # Normalize to -1 to 1
        edge = true_prob - implied_prob

        # Cap at reasonable bounds
        return max(-1.0, min(1.0, edge))

    def _calculate_volatility_score(
        self, mean: float, std: float, role_tag: Optional[RoleTag] = None
    ) -> float:
        """
        Calculate volatility score.

        Args:
            mean: Projected mean value
            std: Standard deviation
            role_tag: Optional role context

        Returns:
            Volatility score (0-1)
        """
        if mean <= 0:
            return 0.5  # Neutral

        # Coefficient of variation
        cv = std / mean

        # Role-based adjustment
        if role_tag:
            # Bench players and specialists have higher volatility
            if role_tag.role.value in ["bench_microwave", "gravity_only", "three_and_d"]:
                cv *= 1.2

        # Normalize CV to 0-1 (CV of 0.5 = high volatility)
        volatility = min(cv / 0.5, 1.0)

        return max(0.0, min(volatility, 1.0))

    def _generate_recommendation(
        self,
        value_score: float,
        volatility_score: float,
        fragility_index: float,
        implied_prob: float,
        prop_line: PropLine,
    ) -> tuple[Literal["higher", "lower", "avoid"], float]:
        """
        Generate recommendation and confidence.

        Args:
            value_score: EV vs book
            volatility_score: Outcome variance
            fragility_index: Script dependence
            implied_prob: Our estimated prob of going over
            prop_line: The prop line

        Returns:
            Tuple of (recommendation, confidence)
        """
        # Check minimum EV threshold
        if abs(value_score) < self.settings.prop_risk.min_ev_threshold:
            return ("avoid", 0.3)

        # Check if too fragile
        if fragility_index > self.settings.scripts.fragility_high_threshold:
            # High fragility = avoid unless exceptional EV
            if abs(value_score) < self.settings.prop_risk.high_ev_threshold:
                return ("avoid", 0.5)

        # Determine side
        if value_score > 0:
            # Over has value
            side: Literal["higher", "lower"] = "higher"
        else:
            # Under has value
            side = "lower"

        # Calculate confidence
        confidence = self._calculate_confidence(
            abs(value_score), volatility_score, fragility_index
        )

        return (side, confidence)

    def _calculate_confidence(
        self, abs_value: float, volatility: float, fragility: float
    ) -> float:
        """
        Calculate recommendation confidence.

        Args:
            abs_value: Absolute value score
            volatility: Volatility score
            fragility: Fragility index

        Returns:
            Confidence (0-1)
        """
        # Base confidence from value
        if abs_value >= 0.15:
            base = 0.9
        elif abs_value >= 0.10:
            base = 0.8
        elif abs_value >= 0.05:
            base = 0.7
        else:
            base = 0.5

        # Penalty for volatility
        vol_penalty = volatility * self.settings.prop_risk.volatility_penalty_weight

        # Penalty for fragility
        frag_penalty = fragility * self.settings.prop_risk.fragility_penalty_weight

        confidence = base - vol_penalty - frag_penalty

        return max(0.0, min(confidence, 1.0))

    def _generate_risk_tags(
        self,
        value_score: float,
        volatility_score: float,
        fragility_index: float,
        role_tag: Optional[RoleTag] = None,
    ) -> list[str]:
        """
        Generate warning tags for UI.

        Args:
            value_score: EV score
            volatility_score: Volatility score
            fragility_index: Fragility index
            role_tag: Optional role context

        Returns:
            List of warning tags
        """
        tags = []

        if abs(value_score) < self.settings.prop_risk.min_ev_threshold:
            tags.append("low_ev")

        if volatility_score > 0.7:
            tags.append("high_variance")

        if fragility_index > self.settings.scripts.fragility_high_threshold:
            tags.append("fragile")
        elif fragility_index < self.settings.scripts.fragility_low_threshold:
            tags.append("robust")

        if role_tag and role_tag.confidence < 0.5:
            tags.append("uncertain_role")

        if value_score > self.settings.prop_risk.high_ev_threshold:
            tags.append("strong_value")

        return tags

    def _calculate_script_weighted_prob(
        self, fragility_analysis: FragilityAnalysis, line: float
    ) -> float:
        """
        Calculate probability-weighted prob of hitting line.

        Args:
            fragility_analysis: Script analysis with probabilities
            line: Line to evaluate

        Returns:
            Weighted probability of going over
        """
        if not fragility_analysis.scripts:
            return 0.5

        total_weighted_prob = 0.0
        total_prob = 0.0

        for script_proj in fragility_analysis.scripts:
            if script_proj.p_hit_line is not None:
                total_weighted_prob += script_proj.probability * script_proj.p_hit_line
                total_prob += script_proj.probability

        if total_prob == 0:
            return 0.5

        return total_weighted_prob / total_prob

    def _calculate_normal_prob(self, mean: float, std: float, line: float) -> float:
        """
        Calculate probability using normal distribution.

        Args:
            mean: Projected mean
            std: Standard deviation
            line: Line to evaluate

        Returns:
            Probability of going over line
        """
        if std <= 0:
            # No variance, deterministic
            return 1.0 if mean > line else 0.0

        import math

        z_score = (line - mean) / std
        # P(X > line) = 1 - CDF(line)
        p_under = 0.5 * (1.0 + math.erf(z_score / math.sqrt(2.0)))
        return 1.0 - p_under
