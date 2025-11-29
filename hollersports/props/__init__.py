"""
Props module - Prop projections and risk scoring.

Combines base projections with venue, role, and script analysis
to produce comprehensive risk profiles for each prop.
"""

from hollersports.props.models import PropRiskProfile
from hollersports.props.prop_risk_scorer import PropRiskScorer

__all__ = ["PropRiskProfile", "PropRiskScorer"]
