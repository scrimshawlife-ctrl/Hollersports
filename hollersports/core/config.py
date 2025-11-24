"""
Configuration management with SEED enforcement.

ABX-Core v1.2 Compliance:
- All behavior is config-driven
- Deterministic: same config + same data = same output
- Provenance: track seed, version, timestamps
- No hidden magic numbers
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, ClassVar, Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ProvenanceMetadata(BaseModel):
    """Tracks provenance of a computation run."""

    seed: int = Field(description="Random seed for reproducibility")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    version: str = Field(default="0.1.0")
    config_hash: str = Field(description="Hash of config used for this run")

    def model_post_init(self, __context: Any) -> None:
        """Generate config hash if not provided."""
        if not self.config_hash:
            # Will be set by the system after config is loaded
            self.config_hash = "pending"


class VenueSettings(BaseModel):
    """Configuration for VenueImpactEngine."""

    enabled: bool = Field(default=True, description="Enable venue impact adjustments")
    arenas_data_path: str = Field(
        default="config/arenas.json", description="Path to arena dataset"
    )
    default_pace_modifier: float = Field(
        default=1.0, description="Default pace modifier if venue unknown"
    )
    default_three_point_modifier: float = Field(
        default=1.0, description="Default 3P modifier if venue unknown"
    )
    altitude_threshold_m: int = Field(
        default=1000, description="Altitude (meters) to apply high-altitude effects"
    )


class RoleSettings(BaseModel):
    """Configuration for RolePriorityTagger."""

    enabled: bool = Field(default=True, description="Enable role tagging")
    min_games_for_inference: int = Field(
        default=5, description="Minimum recent games needed for role inference"
    )
    usage_hinge_threshold: float = Field(
        default=28.0, description="USG% threshold for usage_hinge tag"
    )
    high_assist_threshold: float = Field(
        default=25.0, description="AST% threshold for playmaker roles"
    )
    glass_cleaner_trb_threshold: float = Field(
        default=18.0, description="TRB% threshold for glass_cleaner tag"
    )
    confidence_decay_per_missing_game: float = Field(
        default=0.05, description="Confidence penalty per missing recent game"
    )


class ScriptSettings(BaseModel):
    """Configuration for GameScriptSimulator."""

    enabled: bool = Field(default=True, description="Enable game script simulation")
    num_scripts_per_matchup: int = Field(
        default=5, description="Number of plausible scripts to generate"
    )
    pace_band_width: float = Field(
        default=3.0, description="Possessions +/- for pace variation"
    )
    fragility_high_threshold: float = Field(
        default=0.6, description="Fragility index considered high risk"
    )
    fragility_low_threshold: float = Field(
        default=0.25, description="Fragility index considered robust"
    )


class PropRiskSettings(BaseModel):
    """Configuration for PropRiskScorer."""

    min_ev_threshold: float = Field(
        default=0.03, description="Minimum EV to consider a prop (3%)"
    )
    high_ev_threshold: float = Field(
        default=0.10, description="EV threshold for strong recommendations (10%)"
    )
    volatility_penalty_weight: float = Field(
        default=0.3, description="Weight for volatility in risk score"
    )
    fragility_penalty_weight: float = Field(
        default=0.5, description="Weight for fragility in risk score"
    )


class ParlaySettings(BaseModel):
    """Configuration for ParlayBuilder v2."""

    conservative_max_fragility: float = Field(
        default=0.3, description="Max fragility for conservative mode"
    )
    conservative_min_ev: float = Field(default=0.05, description="Min EV for conservative (5%)")
    balanced_max_fragility: float = Field(
        default=0.5, description="Max fragility for balanced mode"
    )
    balanced_min_ev: float = Field(default=0.03, description="Min EV for balanced (3%)")
    aggressive_max_fragility: float = Field(
        default=0.75, description="Max fragility for aggressive mode"
    )
    aggressive_min_ev: float = Field(default=0.01, description="Min EV for aggressive (1%)")
    max_legs_same_game: int = Field(
        default=2, description="Max legs from same game in a parlay"
    )
    min_legs: int = Field(default=2, description="Minimum parlay legs")
    max_legs: int = Field(default=8, description="Maximum parlay legs")


class Settings(BaseSettings):
    """
    Main settings for HollerSports engine.

    ABX-Core v1.2 compliant: all tunables exposed, deterministic, config-driven.
    """

    model_config = SettingsConfigDict(
        env_prefix="HOLLERSPORTS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core settings
    seed: int = Field(default=42, description="Global random seed for reproducibility")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Logging level"
    )
    config_path: str = Field(default="config/settings.yaml", description="Path to config file")

    # Module settings
    venue: VenueSettings = Field(default_factory=VenueSettings)
    roles: RoleSettings = Field(default_factory=RoleSettings)
    scripts: ScriptSettings = Field(default_factory=ScriptSettings)
    prop_risk: PropRiskSettings = Field(default_factory=PropRiskSettings)
    parlays: ParlaySettings = Field(default_factory=ParlaySettings)

    # API settings
    api_host: str = Field(default="0.0.0.0", description="API server host")
    api_port: int = Field(default=8000, description="API server port")

    # Data settings
    data_cache_ttl_seconds: int = Field(
        default=300, description="TTL for cached external data (5 min)"
    )

    def compute_hash(self) -> str:
        """
        Compute deterministic hash of settings for provenance tracking.

        Returns:
            SHA256 hash of settings as hex string
        """
        # Serialize to deterministic JSON
        config_dict = self.model_dump(mode="json")
        config_json = json.dumps(config_dict, sort_keys=True)
        return hashlib.sha256(config_json.encode()).hexdigest()[:16]

    def create_provenance(self) -> ProvenanceMetadata:
        """
        Create provenance metadata for a run using this config.

        Returns:
            ProvenanceMetadata with seed, timestamp, version, config_hash
        """
        return ProvenanceMetadata(seed=self.seed, config_hash=self.compute_hash())


# Singleton settings instance
_settings: Settings | None = None


def get_settings(config_path: str | None = None, reload: bool = False) -> Settings:
    """
    Get or create singleton Settings instance.

    Args:
        config_path: Optional path to YAML config file
        reload: Force reload of settings

    Returns:
        Settings instance
    """
    global _settings

    if _settings is not None and not reload:
        return _settings

    # Try to load from YAML if path provided or exists
    yaml_config: dict[str, Any] = {}
    if config_path:
        yaml_path = Path(config_path)
    else:
        yaml_path = Path("config/settings.yaml")

    if yaml_path.exists():
        with open(yaml_path, "r") as f:
            yaml_config = yaml.safe_load(f) or {}

    # Create settings (will also pull from env vars)
    _settings = Settings(**yaml_config)
    return _settings


def reset_settings() -> None:
    """Reset settings singleton (useful for testing)."""
    global _settings
    _settings = None
