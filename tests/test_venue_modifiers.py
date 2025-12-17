# FILE: tests/test_venue_modifiers.py
import unittest

from hollersports.engine.context.venue_modifiers import (
    ModifierConfig,
    VenueRecord,
    CoachRecord,
    ModifierLibrary,
    apply_context_modifiers,
    encode_venue_record_from_backtest,
)

class TestVenueModifiers(unittest.TestCase):
    def test_apply_neutral_when_missing(self):
        lib = ModifierLibrary(sport="NBA")
        res = apply_context_modifiers(lib=lib, mu=20.0, sigma=3.0, venue_id="X", coach_id="Y")
        self.assertAlmostEqual(res.mu_adj, 20.0, places=7)
        self.assertAlmostEqual(res.sigma_adj, 3.0, places=7)
        self.assertTrue(res.provenance_hash)

    def test_apply_bounded_modifiers(self):
        cfg = ModifierConfig(max_mean_nudge_frac=0.03, min_sigma_mult=0.90, max_sigma_mult=1.12)
        venues = {
            "CHI": VenueRecord(venue_id="CHI", sport="NBA", mean_nudge_frac=0.03, sigma_mult=1.12, meta={})
        }
        coaches = {
            "C1": CoachRecord(coach_id="C1", sport="NBA", sigma_mult=1.10, mean_nudge_frac=0.03, meta={})
        }
        lib = ModifierLibrary(sport="NBA", config=cfg, venues=venues, coaches=coaches)

        res = apply_context_modifiers(lib=lib, mu=100.0, sigma=10.0, venue_id="CHI", coach_id="C1")

        # mu nudge capped at 0.03 then applied at half strength => 1 + 0.015
        self.assertAlmostEqual(res.mu_adj, 101.5, places=6)

        # sigma_mult = 1.12*1.10 = 1.232 capped to 1.12
        self.assertAlmostEqual(res.sigma_adj, 11.2, places=6)

    def test_encode_from_backtest_clamps(self):
        cfg = ModifierConfig(max_mean_nudge_frac=0.03, min_sigma_mult=0.90, max_sigma_mult=1.12)

        rec = encode_venue_record_from_backtest(
            sport="NBA",
            venue_id="MSG",
            raw_mean_delta_frac=0.25,   # too big -> clamp
            raw_sigma_mult=2.0,         # too big -> clamp
            cfg=cfg,
        )
        self.assertEqual(rec.venue_id, "MSG")
        self.assertAlmostEqual(rec.mean_nudge_frac, 0.03, places=7)
        self.assertAlmostEqual(rec.sigma_mult, 1.12, places=7)

if __name__ == "__main__":
    unittest.main()
