"""
GameScriptSimulator - Enumerate plausible game scripts and measure fragility.

Responsibilities:
- Generate likely game scripts based on matchup context
- Re-project player stats under each script scenario
- Calculate fragility index (script dependence)
- Identify dominant scripts for prop hitting
"""

import math
from typing import Optional

from hollersports.core.config import Settings, get_settings
from hollersports.core.models import MatchupContext, PlayerProjection, StatCategory
from hollersports.scripts.models import FragilityAnalysis, GameScript, ScriptProjection


class GameScriptSimulator:
    """
    Simulator for enumerating game scripts and measuring prop fragility.

    Generates 3-5 plausible scripts per matchup based on:
    - Team pace, offensive/defensive ratings
    - Spread and total (if available)
    - Injuries and back-to-back status

    For each script, re-projects player stats and evaluates prop lines.
    Computes fragility index: how dependent a prop is on narrow scripts.
    """

    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize GameScriptSimulator.

        Args:
            settings: Settings instance (will load default if not provided)
        """
        self.settings = settings or get_settings()

    def simulate_scripts(
        self, matchup: MatchupContext, base_projection: PlayerProjection
    ) -> list[ScriptProjection]:
        """
        Generate plausible game scripts for a matchup.

        Args:
            matchup: Matchup context with team stats, spread, total
            base_projection: Base player projection (before script adjustments)

        Returns:
            List of ScriptProjection objects with probabilities
        """
        if not self.settings.scripts.enabled:
            # Script simulation disabled, return single balanced script
            return [
                ScriptProjection(
                    script=GameScript.BALANCED,
                    probability=1.0,
                    proj_pts=base_projection.proj_pts,
                    proj_reb=base_projection.proj_reb,
                    proj_ast=base_projection.proj_ast,
                    std_dev=base_projection.pts_std,
                )
            ]

        scripts: list[ScriptProjection] = []

        # Calculate matchup characteristics
        avg_pace = (matchup.home_team.pace + matchup.away_team.pace) / 2
        avg_off_rating = (matchup.home_team.off_rating + matchup.away_team.off_rating) / 2
        pace_band = self.settings.scripts.pace_band_width

        # Always include a balanced script
        balanced_prob = 0.30  # Base probability for balanced
        scripts.append(
            self._create_script_projection(
                GameScript.BALANCED,
                balanced_prob,
                base_projection,
                pace_modifier=1.0,
                scoring_modifier=1.0,
            )
        )

        remaining_prob = 1.0 - balanced_prob

        # Determine likely scripts based on matchup context
        likely_scripts = self._identify_likely_scripts(matchup, avg_pace, avg_off_rating)

        # Distribute remaining probability among likely scripts
        if likely_scripts:
            prob_per_script = remaining_prob / len(likely_scripts)

            for script, pace_mod, scoring_mod in likely_scripts:
                scripts.append(
                    self._create_script_projection(
                        script,
                        prob_per_script,
                        base_projection,
                        pace_modifier=pace_mod,
                        scoring_modifier=scoring_mod,
                    )
                )

        # Normalize probabilities to sum to 1.0
        total_prob = sum(s.probability for s in scripts)
        if total_prob > 0:
            scripts = [
                ScriptProjection(
                    script=s.script,
                    probability=s.probability / total_prob,
                    proj_pts=s.proj_pts,
                    proj_reb=s.proj_reb,
                    proj_ast=s.proj_ast,
                    std_dev=s.std_dev,
                    line=s.line,
                    p_hit_line=s.p_hit_line,
                )
                for s in scripts
            ]

        return scripts

    def _identify_likely_scripts(
        self, matchup: MatchupContext, avg_pace: float, avg_off_rating: float
    ) -> list[tuple[GameScript, float, float]]:
        """
        Identify likely scripts based on matchup characteristics.

        Returns:
            List of (GameScript, pace_modifier, scoring_modifier) tuples
        """
        scripts: list[tuple[GameScript, float, float]] = []

        # Pace-based scripts
        if avg_pace >= 102.0:  # High pace teams
            scripts.append((GameScript.PACE_UP, 1.06, 1.0))
        if avg_pace <= 98.0:  # Slow pace teams
            scripts.append((GameScript.PACE_DOWN, 0.94, 1.0))

        # Scoring-based scripts
        if avg_off_rating >= 118.0:  # High-powered offenses
            scripts.append((GameScript.SHOOTOUT, 1.0, 1.08))
        if avg_off_rating <= 110.0:  # Weak offenses
            scripts.append((GameScript.GRIND, 1.0, 0.92))

        # Blowout potential
        if matchup.spread is not None and abs(matchup.spread) >= 8.0:
            # Large spread = blowout risk
            scripts.append((GameScript.BLOWOUT, 0.95, 0.90))

        # If back-to-back for either team, favor grind/pace_down
        if matchup.home_team.is_back_to_back or matchup.away_team.is_back_to_back:
            if GameScript.PACE_DOWN not in [s[0] for s in scripts]:
                scripts.append((GameScript.PACE_DOWN, 0.94, 1.0))

        # Limit to configured number of scripts (minus the balanced one)
        max_scripts = self.settings.scripts.num_scripts_per_matchup - 1
        return scripts[:max_scripts]

    def _create_script_projection(
        self,
        script: GameScript,
        probability: float,
        base_projection: PlayerProjection,
        pace_modifier: float,
        scoring_modifier: float,
    ) -> ScriptProjection:
        """
        Create a ScriptProjection by applying modifiers to base projection.

        Args:
            script: Game script type
            probability: Probability of this script
            base_projection: Base projection to modify
            pace_modifier: Pace adjustment (1.0 = no change)
            scoring_modifier: Scoring efficiency adjustment (1.0 = no change)

        Returns:
            ScriptProjection with adjusted stats
        """
        # Apply pace modifier to volume stats
        pts = base_projection.proj_pts * pace_modifier * scoring_modifier
        reb = base_projection.proj_reb * pace_modifier
        ast = base_projection.proj_ast * pace_modifier

        # Blowout script reduces starters' stats (early exit)
        if script == GameScript.BLOWOUT:
            pts *= 0.85
            reb *= 0.85
            ast *= 0.85

        # Calculate std dev (variance increases with pace)
        base_std = base_projection.pts_std if base_projection.pts_std > 0 else pts * 0.15
        std_dev = base_std * math.sqrt(pace_modifier)

        return ScriptProjection(
            script=script,
            probability=probability,
            proj_pts=pts,
            proj_reb=reb,
            proj_ast=ast,
            std_dev=std_dev,
        )

    def evaluate_line_across_scripts(
        self,
        scripts: list[ScriptProjection],
        line: float,
        stat: StatCategory = StatCategory.POINTS,
    ) -> list[ScriptProjection]:
        """
        Evaluate a prop line across all scripts.

        Updates each ScriptProjection with line and p_hit_line.

        Args:
            scripts: List of script projections
            line: Book line to evaluate
            stat: Stat category (POINTS, REBOUNDS, ASSISTS)

        Returns:
            Updated list of ScriptProjection objects with p_hit_line set
        """
        updated_scripts = []

        for script_proj in scripts:
            # Get projected value for this stat
            if stat == StatCategory.POINTS:
                proj_value = script_proj.proj_pts
            elif stat == StatCategory.REBOUNDS:
                proj_value = script_proj.proj_reb
            elif stat == StatCategory.ASSISTS:
                proj_value = script_proj.proj_ast
            else:
                proj_value = script_proj.proj_pts

            # Calculate p_hit using normal distribution approximation
            # P(X > line) = 1 - CDF(line)
            std = max(script_proj.std_dev, 0.01)  # Avoid division by zero
            z_score = (line - proj_value) / std
            p_under = self._normal_cdf(z_score)
            p_over = 1.0 - p_under

            updated_scripts.append(
                ScriptProjection(
                    script=script_proj.script,
                    probability=script_proj.probability,
                    proj_pts=script_proj.proj_pts,
                    proj_reb=script_proj.proj_reb,
                    proj_ast=script_proj.proj_ast,
                    std_dev=script_proj.std_dev,
                    line=line,
                    p_hit_line=p_over,
                )
            )

        return updated_scripts

    def compute_fragility(
        self, scripts: list[ScriptProjection], line: float | None = None
    ) -> FragilityAnalysis:
        """
        Compute fragility index from script projections.

        Fragility measures how dependent a prop is on specific scripts.
        High fragility = prop only hits in one narrow script.
        Low fragility = prop hits across multiple scripts robustly.

        Args:
            scripts: List of script projections (with p_hit_line if evaluating a line)
            line: Optional line being evaluated

        Returns:
            FragilityAnalysis with fragility index and supporting metrics
        """
        if not scripts:
            return FragilityAnalysis(
                scripts=[],
                fragility_index=1.0,
                script_diversity=0.0,
                weighted_mean=0.0,
                weighted_std=0.0,
            )

        # Calculate weighted mean and std
        total_prob = sum(s.probability for s in scripts)
        if total_prob == 0:
            total_prob = 1.0

        weighted_mean = sum(s.proj_pts * s.probability for s in scripts) / total_prob
        weighted_variance = (
            sum(s.probability * ((s.proj_pts - weighted_mean) ** 2) for s in scripts)
            / total_prob
        )
        weighted_std = math.sqrt(weighted_variance)

        # Script diversity (entropy-like measure)
        # Higher diversity = more evenly distributed
        script_diversity = self._calculate_diversity(scripts)

        # Fragility index
        if line is not None and all(s.p_hit_line is not None for s in scripts):
            # Line-based fragility: how concentrated is the "hit" probability?
            fragility_index = self._calculate_line_fragility(scripts)
            dominant_script = self._find_dominant_script(scripts)
        else:
            # Projection-based fragility: variance across scripts
            if weighted_mean > 0:
                cv = weighted_std / weighted_mean  # Coefficient of variation
                fragility_index = min(cv / 0.5, 1.0)  # Normalize to 0-1
            else:
                fragility_index = 0.5
            dominant_script = None

        return FragilityAnalysis(
            scripts=scripts,
            fragility_index=fragility_index,
            dominant_script=dominant_script,
            script_diversity=script_diversity,
            weighted_mean=weighted_mean,
            weighted_std=weighted_std,
        )

    def _calculate_line_fragility(self, scripts: list[ScriptProjection]) -> float:
        """
        Calculate fragility based on how concentrated hit probability is.

        High fragility = one script dominates the hit probability.
        Low fragility = multiple scripts contribute evenly.

        Returns:
            Fragility index (0-1)
        """
        # Get weighted hit probability for each script
        weighted_hits = [
            s.probability * (s.p_hit_line or 0.0) for s in scripts if s.p_hit_line is not None
        ]

        if not weighted_hits or sum(weighted_hits) == 0:
            return 0.5  # Neutral fragility

        total_hit_prob = sum(weighted_hits)

        # Calculate concentration (Herfindahl index)
        # Higher concentration = higher fragility
        concentration = sum((h / total_hit_prob) ** 2 for h in weighted_hits if total_hit_prob > 0)

        # Normalize: perfect concentration = 1.0, perfect distribution = 1/N
        n = len(weighted_hits)
        if n == 1:
            return 1.0  # Maximum fragility
        min_concentration = 1.0 / n
        fragility = (concentration - min_concentration) / (1.0 - min_concentration)

        return max(0.0, min(fragility, 1.0))

    def _find_dominant_script(self, scripts: list[ScriptProjection]) -> GameScript | None:
        """Find the script most responsible for prop hitting."""
        weighted_hits = [
            (s.script, s.probability * (s.p_hit_line or 0.0))
            for s in scripts
            if s.p_hit_line is not None
        ]

        if not weighted_hits:
            return None

        return max(weighted_hits, key=lambda x: x[1])[0]

    def _calculate_diversity(self, scripts: list[ScriptProjection]) -> float:
        """
        Calculate script diversity (entropy-based).

        Returns:
            Diversity score (0-1), higher = more diverse
        """
        if len(scripts) <= 1:
            return 0.0

        total_prob = sum(s.probability for s in scripts)
        if total_prob == 0:
            return 0.0

        # Calculate Shannon entropy
        entropy = -sum(
            (s.probability / total_prob) * math.log2(s.probability / total_prob + 1e-10)
            for s in scripts
        )

        # Normalize by max entropy (log2(n))
        max_entropy = math.log2(len(scripts))
        if max_entropy == 0:
            return 0.0

        return entropy / max_entropy

    def _normal_cdf(self, z: float) -> float:
        """
        Approximate cumulative distribution function for standard normal.

        Uses error function approximation.

        Args:
            z: Z-score

        Returns:
            P(Z <= z)
        """
        return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
