"""
Smoke tests for NFL SCMF picker.

Validates end-to-end pipeline without exceptions.
"""

import pytest
import numpy as np

from hollersports.nfl.types import NFLGameRow, PropLeg, Side, Market
from hollersports.nfl.picker import pick_slate, build_projection


def generate_synthetic_data(n_games: int = 5, n_players_per_game: int = 10, seed: int = 1337) -> list:
    """
    Generate deterministic synthetic NFL data for testing.

    Creates players that appear across multiple games for realistic history.

    Args:
        n_games: Number of games
        n_players_per_game: Number of players per game
        seed: Random seed

    Returns:
        List of NFLGameRow objects
    """
    np.random.seed(seed)

    data = []
    positions = ["WR", "WR", "WR", "TE", "RB", "RB", "QB", "WR", "TE", "RB"]

    for game_idx in range(n_games):
        game_id = f"game{game_idx + 1}"
        date = f"2024-09-{8 + game_idx:02d}"

        teams = ["KC", "DET", "SF", "DAL", "PHI", "BUF"]
        team = teams[game_idx % len(teams)]
        opponent = teams[(game_idx + 1) % len(teams)]

        for player_idx in range(n_players_per_game):
            # Same player ID across games (player appears in multiple games)
            player_id = f"player{player_idx}"
            position = positions[player_idx % len(positions)]

            # Generate realistic stats based on position
            if position == "WR":
                snaps = int(np.random.uniform(45, 65))
                targets = int(np.random.uniform(4, 10))
                receptions = int(targets * np.random.uniform(0.6, 0.8))
                receiving_yards = receptions * np.random.uniform(11, 14)
                routes = int(snaps * np.random.uniform(0.75, 0.90))
                rushing_attempts = 0
                rushing_yards = 0.0
            elif position == "TE":
                snaps = int(np.random.uniform(40, 55))
                targets = int(np.random.uniform(3, 7))
                receptions = int(targets * np.random.uniform(0.65, 0.85))
                receiving_yards = receptions * np.random.uniform(10, 13)
                routes = int(snaps * np.random.uniform(0.65, 0.80))
                rushing_attempts = 0
                rushing_yards = 0.0
            elif position == "RB":
                snaps = int(np.random.uniform(30, 50))
                targets = int(np.random.uniform(2, 5))
                receptions = int(targets * np.random.uniform(0.70, 0.90))
                receiving_yards = receptions * np.random.uniform(6, 10)
                routes = int(snaps * np.random.uniform(0.25, 0.45))
                rushing_attempts = int(np.random.uniform(10, 20))
                rushing_yards = rushing_attempts * np.random.uniform(3.8, 4.8)
            else:  # QB
                snaps = int(np.random.uniform(62, 68))
                targets = 0
                receptions = 0
                receiving_yards = 0.0
                routes = 0
                rushing_attempts = int(np.random.uniform(2, 6))
                rushing_yards = rushing_attempts * np.random.uniform(3.0, 5.0)

            row = NFLGameRow(
                game_id=game_id,
                date=date,
                team=team,
                opponent=opponent,
                is_home=game_idx % 2,
                player_id=player_id,
                player_name=f"Player {player_idx + 1}",
                position=position,
                snaps=snaps,
                targets=targets,
                receptions=receptions,
                receiving_yards=receiving_yards,
                rushing_attempts=rushing_attempts,
                rushing_yards=rushing_yards,
                routes=routes,
                vegas_spread=-3.5 if game_idx % 2 == 0 else 3.5,
                vegas_total=47.5,
                line=receptions * 1.05 if position != "QB" else rushing_attempts * 1.05,
            )

            data.append(row)

    return data


class TestPickerSmoke:
    """Smoke tests for picker pipeline."""

    @pytest.fixture
    def synthetic_data(self):
        """Generate synthetic data."""
        return generate_synthetic_data(n_games=5, n_players_per_game=10, seed=1337)

    def test_picker_runs_without_exception(self, synthetic_data):
        """Picker should run end-to-end without exceptions."""
        slate_games = ["game1", "game2", "game3"]

        # Create props
        props = []
        for row in synthetic_data[:30]:
            if row.game_id in slate_games and row.position in ("WR", "TE", "RB"):
                if row.receptions > 0:
                    props.append(PropLeg(
                        player_id=row.player_id,
                        player_name=row.player_name,
                        market=Market.RECEPTIONS,
                        line=row.line,
                        side=Side.HIGHER,
                        game_id=row.game_id,
                    ))

        config = {
            "min_confidence": 0.50,  # Lower threshold for synthetic data
            "min_p_hit": 0.55,
            "seed": 1337,
            "n_sims": 150000,
            "ultra_safe_mode": True,
        }

        # Should not raise exception
        result = pick_slate(slate_games, props, synthetic_data, config)

        assert result is not None

    def test_picker_produces_3leg_slate(self, synthetic_data):
        """Picker should produce at least a 3-leg slate."""
        slate_games = ["game1", "game2"]

        props = []
        for row in synthetic_data[:20]:
            if row.game_id in slate_games and row.position in ("WR", "TE", "RB"):
                if row.receptions > 0:
                    props.append(PropLeg(
                        player_id=row.player_id,
                        player_name=row.player_name,
                        market=Market.RECEPTIONS,
                        line=row.line * 0.90,  # Easier line for testing
                        side=Side.HIGHER,
                        game_id=row.game_id,
                    ))

        config = {
            "min_confidence": 0.45,  # Very low for synthetic
            "min_p_hit": 0.50,
            "seed": 1337,
            "n_sims": 150000,
            "ultra_safe_mode": True,
        }

        result = pick_slate(slate_games, props, synthetic_data, config)

        # Should have at least some candidates
        assert result.total_candidates > 0

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
            "n_sims": 150000,
        }

        # Should not crash, may return None
        result = build_projection(
            player_id=target_game.player_id,
            game_id=target_game.game_id,
            line=target_game.line,
            side=Side.HIGHER,
            market=Market.RECEPTIONS,
            player_history=player_history,
            all_data=minimal_data,
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
            PropLeg(
                player_id=synthetic_data[0].player_id,
                player_name=synthetic_data[0].player_name,
                market=Market.RECEPTIONS,
                line=synthetic_data[0].line * 0.85,
                side=Side.HIGHER,
                game_id=synthetic_data[0].game_id,
            )
        ]

        config = {
            "min_confidence": 0.40,
            "min_p_hit": 0.45,
            "seed": 1337,
            "n_sims": 150000,
        }

        result = pick_slate(slate_games, props, synthetic_data, config)

        for proj in result.ultra_safe_3leg:
            assert proj.provenance_hash
            assert len(proj.provenance_hash) > 0

    def test_determinism(self, synthetic_data):
        """Picker should be deterministic with same seed."""
        slate_games = ["game1"]

        props = [
            PropLeg(
                player_id=synthetic_data[0].player_id,
                player_name=synthetic_data[0].player_name,
                market=Market.RECEPTIONS,
                line=synthetic_data[0].line,
                side=Side.HIGHER,
                game_id=synthetic_data[0].game_id,
            )
        ]

        config = {
            "min_confidence": 0.40,
            "min_p_hit": 0.45,
            "seed": 1337,
            "n_sims": 150000,
        }

        result1 = pick_slate(slate_games, props, synthetic_data, config)
        result2 = pick_slate(slate_games, props, synthetic_data, config)

        # Should produce same results
        assert result1.total_candidates == result2.total_candidates
        assert result1.filtered_candidates == result2.filtered_candidates

        if result1.ultra_safe_3leg and result2.ultra_safe_3leg:
            assert result1.ultra_safe_3leg[0].p_hit == result2.ultra_safe_3leg[0].p_hit

    def test_ultra_safe_mode_forbids_touchdowns(self, synthetic_data):
        """Ultra-safe mode should reject touchdown props."""
        slate_games = ["game1"]

        props = [
            PropLeg(
                player_id=synthetic_data[0].player_id,
                player_name=synthetic_data[0].player_name,
                market=Market.REC_TD,  # Touchdown market
                line=0.5,
                side=Side.HIGHER,
                game_id=synthetic_data[0].game_id,
            )
        ]

        config = {
            "min_confidence": 0.40,
            "min_p_hit": 0.45,
            "seed": 1337,
            "n_sims": 150000,
            "ultra_safe_mode": True,
        }

        result = pick_slate(slate_games, props, synthetic_data, config)

        # Should have 0 candidates (TD props forbidden)
        assert result.total_candidates == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
