# FILE: tests/test_reset_state.py
import unittest

from hollersports.engine.reset_state import (
    init_new_slate_state,
    assert_state_matches_inputs,
    hard_reset_runtime_artifacts,
)

class TestResetState(unittest.TestCase):
    def test_new_state_has_empty_artifacts(self):
        games = {"games": [{"game_id": "G1"}]}
        lines = {"k1": {"line": 10.5}}
        st = init_new_slate_state(
            slate_id="NBA_2025-12-17",
            sport="NBA",
            provider="Underdog",
            games_payload=games,
            lines_payload=lines,
        )
        self.assertEqual(st.simulations, {})
        self.assertEqual(st.picks, [])
        self.assertEqual(st.game_context.by_game_id, {})
        self.assertTrue(st.slate.source_fingerprint)
        self.assertTrue(st.market.fingerprint)

    def test_state_mismatch_raises(self):
        games = {"games": [{"game_id": "G1"}]}
        lines = {"k1": {"line": 10.5}}
        st = init_new_slate_state(
            slate_id="NBA_2025-12-17",
            sport="NBA",
            provider="Underdog",
            games_payload=games,
            lines_payload=lines,
        )

        # Change lines -> should fail
        new_lines = {"k1": {"line": 11.5}}
        with self.assertRaises(RuntimeError):
            assert_state_matches_inputs(
                st,
                games_payload=games,
                lines_payload=new_lines,
                provider="Underdog",
            )

    def test_hard_reset_clears_runtime_artifacts(self):
        games = {"games": [{"game_id": "G1"}]}
        lines = {"k1": {"line": 10.5}}
        st = init_new_slate_state(
            slate_id="NBA_2025-12-17",
            sport="NBA",
            provider="Underdog",
            games_payload=games,
            lines_payload=lines,
        )
        st.simulations["x"] = {"ok": True}
        st.picks.append({"leg": "something"})
        st.game_context.by_game_id["G1"] = {"venue": "MSG"}

        hard_reset_runtime_artifacts(st)

        self.assertEqual(st.simulations, {})
        self.assertEqual(st.picks, [])
        self.assertEqual(st.game_context.by_game_id, {})

if __name__ == "__main__":
    unittest.main()
