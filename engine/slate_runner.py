# FILE: HollerSports/engine/slate_runner.py
# ABX-Core / SEED-compliant slate runner.
# Purpose: orchestrate slate processing with proper state isolation.

from __future__ import annotations

from typing import Any, Dict, List, Optional
import logging

from .reset_state import (
    RunState,
    init_new_slate_state,
    assert_state_matches_inputs,
    hard_reset_runtime_artifacts,
)

logger = logging.getLogger(__name__)


class SlateRunner:
    """
    Main orchestrator for processing a slate with proper state management.

    Ensures:
    - No slate leakage between runs
    - Provenance tracking for all inputs
    - Deterministic processing
    - Controlled calibration memory merging
    """

    def __init__(
        self,
        *,
        slate_id: str,
        sport: str,
        provider: str,
        games_payload: Dict[str, Any],
        lines_payload: Dict[str, Any],
        keep_calibration_memory: bool = False,
        prior_calibration: Optional[Any] = None,
    ):
        """
        Initialize a new slate runner with fresh state.

        Args:
            slate_id: Unique identifier for this slate (e.g., "NBA_2025-12-17_EVENING")
            sport: Sport code ("NBA", "NFL", "NHL", etc.)
            provider: Lines provider ("PrizePicks", "Underdog", etc.)
            games_payload: Dict containing game information
            lines_payload: Dict containing market lines snapshot
            keep_calibration_memory: Whether to preserve calibration adjustments
            prior_calibration: Previous calibration memory to merge (if keep_calibration_memory=True)
        """
        self.state = init_new_slate_state(
            slate_id=slate_id,
            sport=sport,
            provider=provider,
            games_payload=games_payload,
            lines_payload=lines_payload,
            keep_calibration_memory=keep_calibration_memory,
            prior_calibration=prior_calibration,
        )

        # Store inputs for validation
        self._games_payload = games_payload
        self._lines_payload = lines_payload
        self._provider = provider

        logger.info(
            f"SlateRunner initialized: {slate_id} ({sport}) | "
            f"Provider: {provider} | "
            f"Source fingerprint: {self.state.slate.source_fingerprint[:16]}..."
        )

    def validate_inputs(self) -> None:
        """
        Validate that current state matches the inputs it was created with.
        Call this before re-running any processing steps.
        """
        assert_state_matches_inputs(
            self.state,
            games_payload=self._games_payload,
            lines_payload=self._lines_payload,
            provider=self._provider,
        )
        logger.debug("State validation passed - inputs match state fingerprints")

    def reset_runtime_artifacts(self) -> None:
        """
        Clear computed artifacts (simulations, picks, game context).
        Use when re-running analysis without changing inputs.
        """
        hard_reset_runtime_artifacts(self.state)
        logger.info("Runtime artifacts reset - ready for fresh computation")

    def compute_game_context(self) -> None:
        """
        Compute per-game contextual modifiers.

        This is where you'd compute:
        - Venue effects (home court advantage)
        - Travel/rest factors
        - Coaching pace adjustments
        - Rotation stability
        - Recent team performance trends

        Integration point: Replace with actual context computation logic.
        """
        logger.info(f"Computing game context for {len(self._games_payload.get('games', []))} games")

        # Example integration point - replace with actual logic
        for game in self._games_payload.get("games", []):
            game_id = game.get("game_id")
            if not game_id:
                continue

            # Placeholder: actual context computation would go here
            context = {
                "venue": game.get("venue", "neutral"),
                "home_team": game.get("home_team"),
                "away_team": game.get("away_team"),
                # Add actual context factors here
            }

            self.state.game_context.by_game_id[game_id] = context

        self.state.game_context.recompute_fingerprint()
        logger.info(
            f"Game context computed: {len(self.state.game_context.by_game_id)} games | "
            f"Fingerprint: {self.state.game_context.fingerprint[:16]}..."
        )

    def run_simulations(self, *, sim_engine: Any = None, iterations: int = 10000) -> None:
        """
        Run Monte Carlo simulations for all markets.

        Integration point: Connect to actual simulation engine.

        Args:
            sim_engine: Simulation engine instance (placeholder for actual engine)
            iterations: Number of Monte Carlo iterations
        """
        logger.info(f"Running simulations: {iterations} iterations per market")

        # Example integration - replace with actual simulation logic
        from .simulation import run_monte_carlo_simulations

        self.state.simulations = run_monte_carlo_simulations(
            state=self.state,
            iterations=iterations,
            sim_engine=sim_engine,
        )

        logger.info(f"Simulations complete: {len(self.state.simulations)} markets simulated")

    def generate_picks(self, *, strategy: str = "edge", min_edge: float = 0.05) -> List[Dict[str, Any]]:
        """
        Generate optimal picks based on simulations and strategy.

        Integration point: Connect to actual pick selection logic.

        Args:
            strategy: Pick selection strategy ("edge", "kelly", "variance_adjusted")
            min_edge: Minimum edge threshold for pick selection

        Returns:
            List of selected picks with metadata
        """
        logger.info(f"Generating picks: strategy={strategy}, min_edge={min_edge}")

        # Example integration - replace with actual pick generation logic
        from .picks_generator import select_optimal_picks

        picks = select_optimal_picks(
            state=self.state,
            strategy=strategy,
            min_edge=min_edge,
        )

        self.state.picks = picks
        logger.info(f"Picks generated: {len(picks)} picks selected")

        return picks

    def run_full_pipeline(
        self,
        *,
        sim_iterations: int = 10000,
        pick_strategy: str = "edge",
        min_edge: float = 0.05,
    ) -> Dict[str, Any]:
        """
        Run the complete slate processing pipeline.

        Args:
            sim_iterations: Monte Carlo iterations
            pick_strategy: Pick selection strategy
            min_edge: Minimum edge threshold

        Returns:
            Complete results with provenance
        """
        logger.info(f"Starting full pipeline for slate: {self.state.slate.slate_id}")

        # Step 1: Validate inputs
        self.validate_inputs()

        # Step 2: Compute game context
        self.compute_game_context()

        # Step 3: Run simulations
        self.run_simulations(iterations=sim_iterations)

        # Step 4: Generate picks
        picks = self.generate_picks(strategy=pick_strategy, min_edge=min_edge)

        # Build results package with full provenance
        results = {
            "slate": {
                "slate_id": self.state.slate.slate_id,
                "sport": self.state.slate.sport,
                "source_fingerprint": self.state.slate.source_fingerprint,
            },
            "market": {
                "provider": self.state.market.provider,
                "fingerprint": self.state.market.fingerprint,
            },
            "picks": picks,
            "stats": {
                "total_picks": len(picks),
                "games_analyzed": len(self.state.game_context.by_game_id),
                "markets_simulated": len(self.state.simulations),
            },
            "provenance": self.state.provenance,
        }

        logger.info(
            f"Pipeline complete: {len(picks)} picks from {len(self.state.simulations)} markets"
        )

        return results

    def export_state(self) -> Dict[str, Any]:
        """
        Export complete state for serialization/storage.
        Useful for debugging or checkpoint/resume workflows.
        """
        return {
            "slate": {
                "slate_id": self.state.slate.slate_id,
                "sport": self.state.slate.sport,
                "as_of_utc_epoch": self.state.slate.as_of_utc_epoch,
                "source_fingerprint": self.state.slate.source_fingerprint,
            },
            "market": {
                "provider": self.state.market.provider,
                "captured_utc_epoch": self.state.market.captured_utc_epoch,
                "fingerprint": self.state.market.fingerprint,
            },
            "game_context": {
                "by_game_id": self.state.game_context.by_game_id,
                "fingerprint": self.state.game_context.fingerprint,
            },
            "calibration": {
                "enabled": self.state.calibration.enabled,
                "adjustments": self.state.calibration.adjustments,
                "fingerprint": self.state.calibration.fingerprint,
            },
            "picks": self.state.picks,
            "provenance": self.state.provenance,
        }
