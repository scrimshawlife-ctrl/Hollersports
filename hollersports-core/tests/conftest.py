from __future__ import annotations
import sys
from pathlib import Path


# Ensure the hollersports_core package in this nested project is importable when
# running tests from the repository root.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
