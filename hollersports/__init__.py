"""
HollerSports - Sports Betting Props Engine

Built on ABX-Core v1.2 principles:
- Modular, deterministic, entropy-minimizing architecture
- SEED enforcement: deterministic behavior with full provenance
- ERS scheduler: composable jobs with clear boundaries
- League-agnostic design (NBA first, extensible)
"""

__version__ = "0.1.0"
__author__ = "Applied Alchemy Labs"

from hollersports.core.config import Settings, get_settings

__all__ = ["Settings", "get_settings", "__version__"]
