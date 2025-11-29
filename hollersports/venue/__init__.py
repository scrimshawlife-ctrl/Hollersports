"""
Venue Impact Engine - Arena-specific modifiers for projections.

Maintains dataset of arena characteristics (altitude, pace, 3P environment, etc.)
and applies appropriate modifiers to player projections.
"""

from hollersports.venue.models import VenueProfile
from hollersports.venue.venue_impact import VenueImpactEngine

__all__ = ["VenueProfile", "VenueImpactEngine"]
