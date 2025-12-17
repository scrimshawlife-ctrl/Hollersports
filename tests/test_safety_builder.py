# FILE: tests/test_safety_builder.py
import unittest

from hollersports.engine.picks.safety_builder import (
    Leg, CandidatePool, SafetyConfig, build_ultra_safe_5_leg_from_core_3
)

class TestSafetyBuilder(unittest.TestCase):
    def test_builds_5_legs(self):
        pool_fp = "POOL_FP"

        # 3 core legs
        core = [
            Leg("a", "NBA", "G1", "P1", "REB", "OVER", 7.5, 0.72, 0.10, 0.08, 0.80, (), pool_fp),
            Leg("b", "NBA", "G1", "P2", "AST", "OVER", 5.5, 0.70, 0.09, 0.07, 0.85, (), pool_fp),
            Leg("c", "NBA", "G2", "P3", "PTS", "UNDER", 21.5, 0.68, 0.06, 0.05, 0.90, (), pool_fp),
        ]

        # candidate universe must include >= 2 valid additions
        legs = tuple(core + [
            Leg("d", "NBA", "G3", "P4", "REB", "OVER", 6.5, 0.66, 0.05, 0.04, 0.85, (), pool_fp),
            Leg("e", "NBA", "G4", "P5", "PTS", "UNDER", 14.5, 0.64, 0.03, 0.03, 0.95, (), pool_fp),
            # should be rejected (same player as core)
            Leg("f", "NBA", "G5", "P1", "PTS", "OVER", 18.5, 0.80, 0.20, 0.15, 1.10, (), pool_fp),
        ])

        pool = CandidatePool(slate_id="S1", provider="Underdog", legs=legs, fingerprint=pool_fp)
        cfg = SafetyConfig(min_p_hit=0.60, max_same_player=1)

        out = build_ultra_safe_5_leg_from_core_3(core3=core, pool=pool, cfg=cfg)
        self.assertEqual(len(out["legs"]), 5)

        # Ensure no duplicate market_key
        keys = [l["market_key"] for l in out["legs"]]
        self.assertEqual(len(keys), len(set(keys)))

if __name__ == "__main__":
    unittest.main()
