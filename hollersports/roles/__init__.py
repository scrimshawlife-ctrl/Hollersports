"""
Role Priority Tagger - Player role inference system.

Tags players with contextual roles (usage_hinge, gravity_only, glass_cleaner, etc.)
based on recent performance and team context.
"""

from hollersports.roles.models import PlayerRole, RoleTag
from hollersports.roles.role_tagger import RolePriorityTagger

__all__ = ["PlayerRole", "RoleTag", "RolePriorityTagger"]
