"""
Unit tests for ParlayBuilder.

Tests parlay construction, mode filtering, and diversification logic.
"""

import pytest

from hollersports.core.config import Settings
from hollersports.parlays import Parlay, ParlayBuilder, ParlayLeg, ParlayMode
from hollersports.props.models import PropRiskProfile


class TestParlayMode:
    """Test ParlayMode enum."""

    def test_mode_values(self) -> None:
        """Test mode enum values."""
        assert ParlayMode.CONSERVATIVE.value == "conservative"
        assert ParlayMode.BALANCED.value == "balanced"
        assert ParlayMode.AGGRESSIVE.value == "aggressive"


class TestParlayLeg:
    """Test ParlayLeg model."""

    def test_create_parlay_leg(self) -> None:
        """Test basic ParlayLeg creation."""
        prop = PropRiskProfile(
            player_id="player123",
            player_name="Test Player",
            stat="points",
            line=24.5,
            value_score=0.08,
            volatility_score=0.35,
            fragility_index=0.28,
            recommended_side="higher",
            confidence=0.75,
            projected_value=26.2,
            implied_prob_over=0.68,
            expected_value=1.7,
        )

        leg = ParlayLeg(prop_risk_profile=prop, odds=-110)

        assert leg.odds == -110
        assert leg.decimal_odds == pytest.approx(1.909, abs=0.01)
        assert leg.implied_prob == pytest.approx(0.5238, abs=0.001)

    def test_american_odds_to_decimal_negative(self) -> None:
        """Test conversion of negative American odds."""
        prop = PropRiskProfile(
            player_id="player123",
            player_name="Test Player",
            stat="points",
            line=24.5,
            value_score=0.08,
            volatility_score=0.35,
            fragility_index=0.28,
            recommended_side="higher",
            confidence=0.75,
            projected_value=26.2,
            implied_prob_over=0.68,
            expected_value=1.7,
        )

        leg = ParlayLeg(prop_risk_profile=prop, odds=-200)

        # -200 → 1 + (100/200) = 1.5
        assert leg.decimal_odds == pytest.approx(1.5, abs=0.01)

    def test_american_odds_to_decimal_positive(self) -> None:
        """Test conversion of positive American odds."""
        prop = PropRiskProfile(
            player_id="player123",
            player_name="Test Player",
            stat="points",
            line=24.5,
            value_score=0.08,
            volatility_score=0.35,
            fragility_index=0.28,
            recommended_side="higher",
            confidence=0.75,
            projected_value=26.2,
            implied_prob_over=0.68,
            expected_value=1.7,
        )

        leg = ParlayLeg(prop_risk_profile=prop, odds=150)

        # +150 → 1 + (150/100) = 2.5
        assert leg.decimal_odds == pytest.approx(2.5, abs=0.01)

    def test_get_display_string(self) -> None:
        """Test display string generation."""
        prop = PropRiskProfile(
            player_id="player123",
            player_name="Devin Booker",
            stat="points",
            line=27.5,
            value_score=0.08,
            volatility_score=0.35,
            fragility_index=0.28,
            recommended_side="higher",
            confidence=0.75,
            projected_value=29.2,
            implied_prob_over=0.68,
            expected_value=1.7,
        )

        leg = ParlayLeg(prop_risk_profile=prop, odds=-110)
        display = leg.get_display_string()

        assert "Devin Booker" in display
        assert "points" in display
        assert "HIGHER" in display
        assert "27.5" in display


class TestParlay:
    """Test Parlay model."""

    def test_create_parlay(self) -> None:
        """Test basic Parlay creation."""
        prop1 = PropRiskProfile(
            player_id="player1",
            player_name="Player 1",
            stat="points",
            line=24.5,
            value_score=0.08,
            volatility_score=0.35,
            fragility_index=0.28,
            recommended_side="higher",
            confidence=0.75,
            projected_value=26.2,
            implied_prob_over=0.68,
            expected_value=1.7,
        )

        leg1 = ParlayLeg(prop_risk_profile=prop1, odds=-110)

        parlay = Parlay(
            parlay_id="test_parlay_1",
            mode=ParlayMode.BALANCED,
            legs=[leg1],
            combined_odds=1.909,
            combined_implied_prob=0.524,
            expected_hit_prob=0.68,
            avg_fragility=0.28,
            avg_confidence=0.75,
            avg_value_score=0.08,
            num_unique_games=1,
            num_unique_stats=1,
        )

        assert parlay.mode == ParlayMode.BALANCED
        assert len(parlay.legs) == 1

    def test_get_potential_payout(self) -> None:
        """Test payout calculation."""
        prop1 = PropRiskProfile(
            player_id="player1",
            player_name="Player 1",
            stat="points",
            line=24.5,
            value_score=0.08,
            volatility_score=0.35,
            fragility_index=0.28,
            recommended_side="higher",
            confidence=0.75,
            projected_value=26.2,
            implied_prob_over=0.68,
            expected_value=1.7,
        )

        leg1 = ParlayLeg(prop_risk_profile=prop1, odds=-110)

        # 2-leg parlay at -110 each: 1.909 × 1.909 ≈ 3.64
        parlay = Parlay(
            parlay_id="test_parlay_1",
            mode=ParlayMode.BALANCED,
            legs=[leg1, leg1],
            combined_odds=3.64,
            combined_implied_prob=0.274,
            expected_hit_prob=0.46,
            avg_fragility=0.28,
            avg_confidence=0.75,
            avg_value_score=0.08,
            num_unique_games=2,
            num_unique_stats=1,
        )

        # $100 stake × 3.64 = $364 payout
        payout = parlay.get_potential_payout(100.0)
        assert payout == pytest.approx(364.0, abs=0.1)

    def test_get_potential_profit(self) -> None:
        """Test profit calculation."""
        prop1 = PropRiskProfile(
            player_id="player1",
            player_name="Player 1",
            stat="points",
            line=24.5,
            value_score=0.08,
            volatility_score=0.35,
            fragility_index=0.28,
            recommended_side="higher",
            confidence=0.75,
            projected_value=26.2,
            implied_prob_over=0.68,
            expected_value=1.7,
        )

        leg1 = ParlayLeg(prop_risk_profile=prop1, odds=-110)

        parlay = Parlay(
            parlay_id="test_parlay_1",
            mode=ParlayMode.BALANCED,
            legs=[leg1, leg1],
            combined_odds=3.64,
            combined_implied_prob=0.274,
            expected_hit_prob=0.46,
            avg_fragility=0.28,
            avg_confidence=0.75,
            avg_value_score=0.08,
            num_unique_games=2,
            num_unique_stats=1,
        )

        # $364 payout - $100 stake = $264 profit
        profit = parlay.get_potential_profit(100.0)
        assert profit == pytest.approx(264.0, abs=0.1)

    def test_get_expected_value(self) -> None:
        """Test EV calculation."""
        prop1 = PropRiskProfile(
            player_id="player1",
            player_name="Player 1",
            stat="points",
            line=24.5,
            value_score=0.08,
            volatility_score=0.35,
            fragility_index=0.28,
            recommended_side="higher",
            confidence=0.75,
            projected_value=26.2,
            implied_prob_over=0.68,
            expected_value=1.7,
        )

        leg1 = ParlayLeg(prop_risk_profile=prop1, odds=-110)

        parlay = Parlay(
            parlay_id="test_parlay_1",
            mode=ParlayMode.BALANCED,
            legs=[leg1],
            combined_odds=1.909,
            combined_implied_prob=0.524,
            expected_hit_prob=0.68,  # Higher than implied
            avg_fragility=0.28,
            avg_confidence=0.75,
            avg_value_score=0.08,
            num_unique_games=1,
            num_unique_stats=1,
        )

        # EV = (0.68 × $190.9) - $100 = $29.81
        ev = parlay.get_expected_value(100.0)
        assert ev > 0  # Positive EV
        assert ev == pytest.approx(29.81, abs=1.0)

    def test_is_positive_ev(self) -> None:
        """Test positive EV detection."""
        prop1 = PropRiskProfile(
            player_id="player1",
            player_name="Player 1",
            stat="points",
            line=24.5,
            value_score=0.08,
            volatility_score=0.35,
            fragility_index=0.28,
            recommended_side="higher",
            confidence=0.75,
            projected_value=26.2,
            implied_prob_over=0.68,
            expected_value=1.7,
        )

        leg1 = ParlayLeg(prop_risk_profile=prop1, odds=-110)

        plus_ev = Parlay(
            parlay_id="plus_ev",
            mode=ParlayMode.BALANCED,
            legs=[leg1],
            combined_odds=1.909,
            combined_implied_prob=0.524,
            expected_hit_prob=0.68,
            avg_fragility=0.28,
            avg_confidence=0.75,
            avg_value_score=0.08,
            num_unique_games=1,
            num_unique_stats=1,
        )

        minus_ev = Parlay(
            parlay_id="minus_ev",
            mode=ParlayMode.BALANCED,
            legs=[leg1],
            combined_odds=1.909,
            combined_implied_prob=0.524,
            expected_hit_prob=0.45,  # Lower than implied
            avg_fragility=0.28,
            avg_confidence=0.75,
            avg_value_score=0.08,
            num_unique_games=1,
            num_unique_stats=1,
        )

        assert plus_ev.is_positive_ev() is True
        assert minus_ev.is_positive_ev() is False

    def test_get_risk_level(self) -> None:
        """Test risk level categorization."""
        prop1 = PropRiskProfile(
            player_id="player1",
            player_name="Player 1",
            stat="points",
            line=24.5,
            value_score=0.08,
            volatility_score=0.35,
            fragility_index=0.28,
            recommended_side="higher",
            confidence=0.75,
            projected_value=26.2,
            implied_prob_over=0.68,
            expected_value=1.7,
        )

        leg1 = ParlayLeg(prop_risk_profile=prop1, odds=-110)

        low_risk = Parlay(
            parlay_id="low",
            mode=ParlayMode.CONSERVATIVE,
            legs=[leg1],
            combined_odds=1.909,
            combined_implied_prob=0.524,
            expected_hit_prob=0.68,
            avg_fragility=0.15,
            avg_confidence=0.85,
            avg_value_score=0.08,
            num_unique_games=1,
            num_unique_stats=1,
        )

        medium_risk = Parlay(
            parlay_id="medium",
            mode=ParlayMode.BALANCED,
            legs=[leg1],
            combined_odds=1.909,
            combined_implied_prob=0.524,
            expected_hit_prob=0.68,
            avg_fragility=0.40,
            avg_confidence=0.70,
            avg_value_score=0.08,
            num_unique_games=1,
            num_unique_stats=1,
        )

        high_risk = Parlay(
            parlay_id="high",
            mode=ParlayMode.AGGRESSIVE,
            legs=[leg1],
            combined_odds=1.909,
            combined_implied_prob=0.524,
            expected_hit_prob=0.68,
            avg_fragility=0.65,
            avg_confidence=0.55,
            avg_value_score=0.08,
            num_unique_games=1,
            num_unique_stats=1,
        )

        assert low_risk.get_risk_level() == "low"
        assert medium_risk.get_risk_level() == "medium"
        assert high_risk.get_risk_level() == "high"


class TestParlayBuilder:
    """Test ParlayBuilder."""

    def test_init(self) -> None:
        """Test builder initialization."""
        builder = ParlayBuilder()
        assert builder.settings is not None

    def test_conservative_mode_filtering(self) -> None:
        """Test that conservative mode applies strict filtering."""
        builder = ParlayBuilder()

        # Create candidates with varying fragility
        candidates = [
            PropRiskProfile(
                player_id="player1",
                player_name="Low Fragility",
                stat="points",
                line=24.5,
                value_score=0.08,
                volatility_score=0.25,
                fragility_index=0.20,  # Low fragility
                recommended_side="higher",
                confidence=0.85,
                projected_value=26.2,
                implied_prob_over=0.68,
                expected_value=1.7,
            ),
            PropRiskProfile(
                player_id="player2",
                player_name="High Fragility",
                stat="rebounds",
                line=7.5,
                value_score=0.08,
                volatility_score=0.35,
                fragility_index=0.65,  # High fragility
                recommended_side="higher",
                confidence=0.60,
                projected_value=8.5,
                implied_prob_over=0.62,
                expected_value=1.0,
            ),
            PropRiskProfile(
                player_id="player3",
                player_name="Low EV",
                stat="assists",
                line=5.5,
                value_score=0.02,  # Low EV
                volatility_score=0.30,
                fragility_index=0.25,
                recommended_side="higher",
                confidence=0.75,
                projected_value=6.0,
                implied_prob_over=0.55,
                expected_value=0.5,
            ),
        ]

        parlay = builder.build_parlay(candidates, ParlayMode.CONSERVATIVE, "test_conservative")

        # Should only include low fragility prop
        assert parlay is not None
        assert len(parlay.legs) == 1
        assert parlay.legs[0].prop_risk_profile.player_name == "Low Fragility"

    def test_balanced_mode_filtering(self) -> None:
        """Test that balanced mode uses medium thresholds."""
        builder = ParlayBuilder()

        candidates = [
            PropRiskProfile(
                player_id="player1",
                player_name="Player 1",
                stat="points",
                line=24.5,
                value_score=0.05,  # Medium EV
                volatility_score=0.35,
                fragility_index=0.45,  # Medium fragility
                recommended_side="higher",
                confidence=0.70,
                projected_value=26.2,
                implied_prob_over=0.65,
                expected_value=1.7,
            ),
            PropRiskProfile(
                player_id="player2",
                player_name="Player 2",
                stat="rebounds",
                line=7.5,
                value_score=0.04,
                volatility_score=0.40,
                fragility_index=0.48,
                recommended_side="higher",
                confidence=0.68,
                projected_value=8.5,
                implied_prob_over=0.63,
                expected_value=1.0,
            ),
        ]

        parlay = builder.build_parlay(candidates, ParlayMode.BALANCED, "test_balanced")

        # Should include both props
        assert parlay is not None
        assert len(parlay.legs) == 2

    def test_aggressive_mode_filtering(self) -> None:
        """Test that aggressive mode accepts higher risk."""
        builder = ParlayBuilder()

        candidates = [
            PropRiskProfile(
                player_id="player1",
                player_name="Risky Prop",
                stat="points",
                line=24.5,
                value_score=0.02,  # Low EV
                volatility_score=0.55,
                fragility_index=0.70,  # High fragility
                recommended_side="higher",
                confidence=0.55,
                projected_value=26.2,
                implied_prob_over=0.60,
                expected_value=1.7,
            ),
        ]

        parlay = builder.build_parlay(candidates, ParlayMode.AGGRESSIVE, "test_aggressive")

        # Should accept risky prop in aggressive mode
        assert parlay is not None
        assert len(parlay.legs) == 1

    def test_diversification_enforcement(self) -> None:
        """Test that diversification is enforced (max 2 legs per game)."""
        settings = Settings(parlays={"max_legs_same_game": 2})
        builder = ParlayBuilder(settings)

        # Create 4 props from same matchup
        candidates = [
            PropRiskProfile(
                player_id=f"same_game_{i}",
                player_name=f"Player {i}",
                stat="points" if i % 2 == 0 else "rebounds",
                line=24.5,
                value_score=0.08,
                volatility_score=0.30,
                fragility_index=0.25,
                recommended_side="higher",
                confidence=0.75,
                projected_value=26.2,
                implied_prob_over=0.68,
                expected_value=1.7,
            )
            for i in range(4)
        ]

        parlay = builder.build_parlay(
            candidates, ParlayMode.BALANCED, "test_diversification", num_legs=4
        )

        # Should only include 2 legs (max_legs_same_game)
        # Note: _extract_matchup_id uses first 3 chars of player_id
        # All start with "sam", so they'll be grouped together
        assert parlay is not None
        assert len(parlay.legs) <= 2

    def test_build_all_modes(self) -> None:
        """Test building parlays for all three modes."""
        builder = ParlayBuilder()

        # Create diverse candidates
        candidates = [
            PropRiskProfile(
                player_id=f"player{i}",
                player_name=f"Player {i}",
                stat="points" if i % 3 == 0 else "rebounds" if i % 3 == 1 else "assists",
                line=24.5 + i,
                value_score=0.08 - (i * 0.01),
                volatility_score=0.30 + (i * 0.05),
                fragility_index=0.20 + (i * 0.08),
                recommended_side="higher",
                confidence=0.80 - (i * 0.05),
                projected_value=26.2,
                implied_prob_over=0.68,
                expected_value=1.7,
            )
            for i in range(6)
        ]

        parlays = builder.build_all_modes(candidates, base_id="multi_mode")

        # All three modes should produce parlays
        assert parlays[ParlayMode.CONSERVATIVE] is not None
        assert parlays[ParlayMode.BALANCED] is not None
        assert parlays[ParlayMode.AGGRESSIVE] is not None

        # Conservative should have fewest legs
        conservative_legs = len(parlays[ParlayMode.CONSERVATIVE].legs)
        aggressive_legs = len(parlays[ParlayMode.AGGRESSIVE].legs)
        assert conservative_legs <= aggressive_legs

    def test_insufficient_candidates(self) -> None:
        """Test that None is returned when insufficient valid candidates."""
        builder = ParlayBuilder()

        # All candidates fail conservative thresholds
        candidates = [
            PropRiskProfile(
                player_id="player1",
                player_name="High Fragility",
                stat="points",
                line=24.5,
                value_score=0.08,
                volatility_score=0.35,
                fragility_index=0.85,  # Too fragile
                recommended_side="higher",
                confidence=0.60,
                projected_value=26.2,
                implied_prob_over=0.62,
                expected_value=1.7,
            ),
        ]

        parlay = builder.build_parlay(candidates, ParlayMode.CONSERVATIVE, "insufficient")

        # Should return None
        assert parlay is None

    def test_avoid_props_excluded(self) -> None:
        """Test that props with 'avoid' recommendation are excluded."""
        builder = ParlayBuilder()

        candidates = [
            PropRiskProfile(
                player_id="player1",
                player_name="Recommended",
                stat="points",
                line=24.5,
                value_score=0.08,
                volatility_score=0.30,
                fragility_index=0.25,
                recommended_side="higher",  # Recommended
                confidence=0.75,
                projected_value=26.2,
                implied_prob_over=0.68,
                expected_value=1.7,
            ),
            PropRiskProfile(
                player_id="player2",
                player_name="Avoided",
                stat="rebounds",
                line=7.5,
                value_score=0.01,
                volatility_score=0.50,
                fragility_index=0.70,
                recommended_side="avoid",  # Avoid
                confidence=0.30,
                projected_value=7.2,
                implied_prob_over=0.48,
                expected_value=-0.2,
            ),
        ]

        parlay = builder.build_parlay(candidates, ParlayMode.BALANCED, "no_avoid")

        # Should only include recommended prop
        assert parlay is not None
        assert len(parlay.legs) == 1
        assert parlay.legs[0].prop_risk_profile.player_name == "Recommended"

    def test_parlay_tags_generation(self) -> None:
        """Test that parlay tags are generated correctly."""
        builder = ParlayBuilder()

        # All robust, high confidence props
        candidates = [
            PropRiskProfile(
                player_id=f"player{i}",
                player_name=f"Player {i}",
                stat="points" if i % 2 == 0 else "rebounds",
                line=24.5,
                value_score=0.10,  # Strong value
                volatility_score=0.25,
                fragility_index=0.18,  # Robust
                recommended_side="higher",
                confidence=0.85,  # High confidence
                projected_value=26.2,
                implied_prob_over=0.70,
                expected_value=1.7,
            )
            for i in range(3)
        ]

        parlay = builder.build_parlay(candidates, ParlayMode.BALANCED, "tagged", num_legs=3)

        assert parlay is not None
        assert "mode_balanced" in parlay.tags
        assert "all_robust" in parlay.tags
        assert "high_confidence" in parlay.tags
        assert "strong_value" in parlay.tags
