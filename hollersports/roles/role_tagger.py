"""
RolePriorityTagger - Infer player roles from recent statistics.

Responsibilities:
- Analyze PlayerStats to infer contextual role
- Apply heuristics based on usage, assist rate, rebounding, etc.
- Assign confidence scores based on signal strength and data quality
- Track role assignment provenance
"""

from typing import Optional

from hollersports.core.config import Settings, get_settings
from hollersports.core.models import PlayerStats, TeamContext
from hollersports.roles.models import PlayerRole, RoleTag


class RolePriorityTagger:
    """
    Engine for inferring player roles from statistical profiles.

    Uses transparent heuristics to tag players with roles like:
    - usage_hinge, tunnel_scorer, glass_cleaner, connector, etc.

    Confidence is based on:
    - How clearly stats match a role pattern
    - Number of recent games available
    - Consistency of signals
    """

    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize RolePriorityTagger.

        Args:
            settings: Settings instance (will load default if not provided)
        """
        self.settings = settings or get_settings()

    def infer_role(
        self, player_stats: PlayerStats, team_context: Optional[TeamContext] = None
    ) -> RoleTag:
        """
        Infer player role from recent statistics.

        Args:
            player_stats: Recent statistical profile
            team_context: Optional team context (future: for relative usage, etc.)

        Returns:
            RoleTag with role assignment and confidence
        """
        if not self.settings.roles.enabled:
            # Role tagging disabled
            return RoleTag(role=PlayerRole.UNKNOWN, confidence=0.0, notes={})

        # Check minimum games requirement
        if player_stats.games_played < self.settings.roles.min_games_for_inference:
            return RoleTag(
                role=PlayerRole.UNKNOWN,
                confidence=0.0,
                notes={"games_played": float(player_stats.games_played)},
            )

        # Apply role inference heuristics
        role, base_confidence, notes = self._classify_role(player_stats)

        # Adjust confidence for data quality
        confidence = self._adjust_confidence_for_data_quality(
            base_confidence, player_stats.games_played
        )

        return RoleTag(role=role, confidence=confidence, notes=notes)

    def _classify_role(
        self, stats: PlayerStats
    ) -> tuple[PlayerRole, float, dict[str, float]]:
        """
        Apply heuristics to classify role.

        Returns:
            Tuple of (role, base_confidence, notes_dict)
        """
        notes: dict[str, float] = {
            "usg_pct": stats.usage_pct,
            "ast_pct": stats.ast_pct,
            "reb_pct": stats.reb_pct,
            "pts_per_game": stats.pts_per_game,
        }

        # High usage primary scorer
        if stats.usage_pct >= self.settings.roles.usage_hinge_threshold:
            if stats.ast_pct >= self.settings.roles.high_assist_threshold:
                # High usage + high assists = primary playmaker
                return PlayerRole.PRIMARY_PLAYMAKER, 0.85, notes
            else:
                # High usage, lower assists = usage hinge scorer
                return PlayerRole.USAGE_HINGE, 0.85, notes

        # Glass cleaner (rebounding specialist)
        if stats.reb_pct >= self.settings.roles.glass_cleaner_trb_threshold:
            if stats.usage_pct < 20.0:
                # High rebounds, low usage = pure glass cleaner
                return PlayerRole.GLASS_CLEANER, 0.80, notes
            else:
                # High rebounds, moderate usage = all-around
                return PlayerRole.ALL_AROUND, 0.70, notes

        # Connector (moderate everything, high assists)
        if (
            stats.ast_pct >= self.settings.roles.high_assist_threshold
            and 15.0 <= stats.usage_pct < self.settings.roles.usage_hinge_threshold
        ):
            return PlayerRole.CONNECTOR, 0.75, notes

        # Tunnel scorer (moderate-high usage, low assists)
        if stats.usage_pct >= 22.0 and stats.ast_pct < 15.0:
            if stats.pts_per_game >= 18.0:
                return PlayerRole.TUNNEL_SCORER, 0.70, notes

        # Three-and-D (moderate 3PM, low usage)
        if stats.fg3m_per_game >= 2.0 and stats.usage_pct < 18.0:
            return PlayerRole.THREE_AND_D, 0.65, notes

        # Bench microwave (scoring off bench)
        # Note: Would need starter/bench info; use minutes as proxy
        if stats.pts_per_game >= 12.0 and stats.min_per_game < 25.0:
            if stats.usage_pct >= 22.0:
                return PlayerRole.BENCH_MICROWAVE, 0.70, notes

        # Rim protector
        if stats.blk_per_game >= 1.5:
            if stats.usage_pct < 18.0:
                return PlayerRole.RIM_PROTECTOR, 0.70, notes

        # Gravity only (low usage, moderate scoring)
        # Hard to detect statistically; would need tracking data
        # Placeholder: low usage, decent 3P volume
        if stats.usage_pct < 15.0 and stats.fg3m_per_game >= 1.5:
            return PlayerRole.GRAVITY_ONLY, 0.50, notes

        # All-around (balanced stats)
        if self._is_balanced_profile(stats):
            return PlayerRole.ALL_AROUND, 0.60, notes

        # Role player (limited, specific function)
        if stats.usage_pct < 15.0 and stats.min_per_game < 25.0:
            return PlayerRole.ROLE_PLAYER, 0.60, notes

        # Unknown (doesn't fit clear pattern)
        return PlayerRole.UNKNOWN, 0.3, notes

    def _is_balanced_profile(self, stats: PlayerStats) -> bool:
        """
        Check if player has a balanced statistical profile.

        Args:
            stats: PlayerStats to check

        Returns:
            True if balanced across pts/reb/ast
        """
        # Moderate in all categories
        pts_ok = 10.0 <= stats.pts_per_game <= 22.0
        reb_ok = 4.0 <= stats.reb_per_game <= 10.0
        ast_ok = 3.0 <= stats.ast_per_game <= 7.0
        usg_ok = 18.0 <= stats.usage_pct <= 26.0

        return pts_ok and reb_ok and ast_ok and usg_ok

    def _adjust_confidence_for_data_quality(
        self, base_confidence: float, games_played: int
    ) -> float:
        """
        Adjust confidence based on data quality.

        More games = higher confidence.
        Fewer games = confidence penalty.

        Args:
            base_confidence: Initial confidence from classification
            games_played: Number of recent games

        Returns:
            Adjusted confidence (0-1)
        """
        min_games = self.settings.roles.min_games_for_inference
        ideal_games = 15  # Ideal sample size

        if games_played >= ideal_games:
            # Full confidence
            return base_confidence

        # Gradually reduce confidence for fewer games
        games_above_min = games_played - min_games
        penalty_per_game = self.settings.roles.confidence_decay_per_missing_game
        penalty = (ideal_games - games_played) * penalty_per_game

        adjusted = base_confidence - penalty
        return max(adjusted, 0.0)

    def tag_role_display(self, role_tag: RoleTag) -> str:
        """
        Generate display-friendly role tag string.

        Args:
            role_tag: RoleTag to format

        Returns:
            Formatted string like "usage_hinge (high conf)" or "connector (medium)"
        """
        if role_tag.confidence >= 0.7:
            conf_label = "high conf"
        elif role_tag.confidence >= 0.5:
            conf_label = "medium"
        else:
            conf_label = "low"

        return f"{role_tag.role.value} ({conf_label})"

    def get_role_impact_on_props(self, role_tag: RoleTag) -> dict[str, str]:
        """
        Get qualitative impact of role on different prop categories.

        Args:
            role_tag: Role tag to analyze

        Returns:
            Dict mapping stat category to impact level (e.g., "high", "medium", "low")
        """
        role = role_tag.role

        # Define role → prop impact mappings
        impact_map: dict[PlayerRole, dict[str, str]] = {
            PlayerRole.USAGE_HINGE: {
                "points": "high",
                "assists": "medium",
                "rebounds": "medium",
            },
            PlayerRole.PRIMARY_PLAYMAKER: {
                "points": "high",
                "assists": "high",
                "rebounds": "medium",
            },
            PlayerRole.GLASS_CLEANER: {
                "points": "low",
                "assists": "low",
                "rebounds": "high",
            },
            PlayerRole.CONNECTOR: {
                "points": "medium",
                "assists": "high",
                "rebounds": "medium",
            },
            PlayerRole.TUNNEL_SCORER: {
                "points": "high",
                "assists": "low",
                "rebounds": "low",
            },
            PlayerRole.THREE_AND_D: {
                "points": "medium",
                "assists": "low",
                "rebounds": "low",
                "three_pointers": "high",
            },
            PlayerRole.BENCH_MICROWAVE: {
                "points": "high",
                "assists": "low",
                "rebounds": "low",
            },
            PlayerRole.RIM_PROTECTOR: {
                "points": "low",
                "assists": "low",
                "rebounds": "medium",
                "blocks": "high",
            },
            PlayerRole.ALL_AROUND: {
                "points": "medium",
                "assists": "medium",
                "rebounds": "medium",
            },
        }

        return impact_map.get(
            role,
            {
                "points": "unknown",
                "assists": "unknown",
                "rebounds": "unknown",
            },
        )
