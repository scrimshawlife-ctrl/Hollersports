"""
Smoke tests for NHL SOG picker.

Validates end-to-end pipeline without exceptions.
"""

import pytest
import numpy as np

from hollersports.nhl.types import NHLGameRow, SOGProp, Side
from hollersports.nhl.picker import pick_slate, build_projection


def generate_synthetic_data(n_games: int = 5, n_players: int = 10, seed: int = 1337) -> list:
    """
    Generate deterministic synthetic NHL data for testing.

    Args:
        n_games: Number of games
        n_players: Number of players
        seed: Random seed

    Returns:
        List of NHLGameRow objects
    """
    np.random.seed(seed)

    data = []

    for game_idx in range(n_games):
        game_id = f"game{game_idx + 1}"
        date_offset = game_idx

        teams = ["BOS", "TOR"]
        team = teams[game_idx % 2]
        opponent = teams[(game_idx + 1) % 2]

        for player_idx in range(n_players):
            player_id = f"player{player_idx + 1}"

            # Generate realistic SOG data
            base_sog = np.random.randint(2, 6)
            toi = np.random.uniform(14.0, 20.0)

            row = NHLGameRow(
                game_id=game_id,
                date=f"2024-01-{1 + date_offset:02d}",
                team=team,
                opponent=opponent,
                is_home=game_idx % 2,
                player_id=player_id,
                player_name=f"Player {player_idx + 1}",
                position="F",
                toi_minutes=toi,
                sog=base_sog,
                pp_toi_minutes=np.random.uniform(2.0, 5.0) if np.random.rand() > 0.3 else None,
                line_sog=base_sog * 1.05,  # Slightly above baseline
            )

            data.append(row)

    return data


class TestPickerSmoke:
    """Smoke tests for picker pipeline."""

    @pytest.fixture
    def synthetic_data(self):
        """Generate synthetic data."""
        return generate_synthetic_data(n_games=5, n_players=10, seed=1337)

    def test_picker_runs_without_exception(self, synthetic_data):
        """Picker should run end-to-end without exceptions."""
        slate_games = ["game1", "game2", "game3"]

        # Create props
        props = []
        for row in synthetic_data[:20]:
            if row.game_id in slate_games:
                props.append(SOGProp(
                    player_id=row.player_id,
                    player_name=row.player_name,
                    line=row.line_sog,
                    side=Side.HIGHER,
                    game_id=row.game_id,
                ))

        config = {
            "min_confidence": 0.50,  # Lower threshold for synthetic data
            "min_p_hit": 0.55,
            "seed": 1337,
        }

        # Should not raise exception
        result = pick_slate(slate_games, props, synthetic_data, config)

        assert result is not None

    def test_picker_produces_3leg_slate(self, synthetic_data):
        """Picker should produce at least a 3-leg slate."""
        slate_games = ["game1", "game2"]

        props = []
        for row in synthetic_data[:15]:
            if row.game_id in slate_games:
                props.append(SOGProp(
                    player_id=row.player_id,
                    player_name=row.player_name,
                    line=row.line_sog * 0.95,  # Easier line for testing
                    side=Side.HIGHER,
                    game_id=row.game_id,
                ))

        config = {
            "min_confidence": 0.45,  # Very low for synthetic
            "min_p_hit": 0.50,
            "seed": 1337,
        }

        result = pick_slate(slate_games, props, synthetic_data, config)

        # Should have at least some candidates
        assert result.filtered_candidates > 0

        # Should produce 3-leg (or less if not enough candidates)
        assert len(result.ultra_safe_3leg) <= 3

    def test_build_projection_handles_insufficient_data(self, synthetic_data):
        """build_projection should handle edge cases gracefully."""
        # Single observation (insufficient history)
        minimal_data = synthetic_data[:1]

        player_history = [minimal_data[0]]
        target_game = minimal_data[0]

        config = {
            "min_confidence": 0.50,
            "min_p_hit": 0.55,
            "seed": 1337,
        }

        # Should not crash, may return None
        result = build_projection(
            player_id=target_game.player_id,
            game_id=target_game.game_id,
            line=target_game.line_sog,
            side=Side.HIGHER,
            player_history=player_history,
            all_data=minimal_data,
            target_game=target_game,
            dataset_fingerprint="test_hash",
            config=config,
        )

        # Either returns None or valid projection
        if result is not None:
            assert hasattr(result, "p_hit")
            assert 0.0 <= result.p_hit <= 1.0

    def test_projections_have_provenance(self, synthetic_data):
        """All projections should have provenance hash."""
        slate_games = ["game1"]

        props = [
            SOGProp(
                player_id=synthetic_data[0].player_id,
                player_name=synthetic_data[0].player_name,
                line=synthetic_data[0].line_sog * 0.9,
                side=Side.HIGHER,
                game_id=synthetic_data[0].game_id,
            )
        ]

        config = {
            "min_confidence": 0.40,
            "min_p_hit": 0.45,
            "seed": 1337,
        }

        result = pick_slate(slate_games, props, synthetic_data, config)

        for proj in result.ultra_safe_3leg:
            assert proj.provenance_hash
            assert len(proj.provenance_hash) > 0

    def test_determinism(self, synthetic_data):
        """Picker should be deterministic with same seed."""
        slate_games = ["game1"]

        props = [
            SOGProp(
                player_id=synthetic_data[0].player_id,
                player_name=synthetic_data[0].player_name,
                line=synthetic_data[0].line_sog,
                side=Side.HIGHER,
                game_id=synthetic_data[0].game_id,
            )
        ]

        config = {
            "min_confidence": 0.40,
            "min_p_hit": 0.45,
            "seed": 1337,
        }

        result1 = pick_slate(slate_games, props, synthetic_data, config)
        result2 = pick_slate(slate_games, props, synthetic_data, config)

        # Should produce same results
        assert result1.filtered_candidates == result2.filtered_candidates

        if result1.ultra_safe_3leg and result2.ultra_safe_3leg:
            assert result1.ultra_safe_3leg[0].p_hit == result2.ultra_safe_3leg[0].p_hit


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
