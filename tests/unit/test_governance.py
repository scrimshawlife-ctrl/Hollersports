from hollersports.governance.authority import Authority, assert_no_live_capital
from hollersports.governance.fail_closed import not_computable
from hollersports.schemas.hashing import packet_hash, stable_json
import pytest


def test_authority_values():
    assert Authority.SHADOW_ONLY.value == "SHADOW_ONLY"
    assert Authority.PROJECTION_ONLY.value == "PROJECTION_ONLY"


def test_assert_no_live_capital_raises():
    with pytest.raises(ValueError, match="capital"):
        assert_no_live_capital({"capital_authority": True})


def test_assert_no_live_capital_forbids_live_approved_mode():
    """Defense-in-depth: LIVE_APPROVED mode is still rejected if present."""
    with pytest.raises(ValueError, match="LIVE_APPROVED"):
        assert_no_live_capital(
            {
                "capital_authority": False,
                "execution_authority": False,
                "mode": "LIVE_APPROVED",
            }
        )


def test_not_computable_shape():
    p = not_computable("SourceHealthPacket.v1", "missing_provenance")
    assert p["status"] == "NOT_COMPUTABLE"
    assert p["authority"] == "SHADOW_ONLY"
    assert p["reason"] == "missing_provenance"
    assert p["capital_authority"] is False
    assert p["execution_authority"] is False


def test_packet_hash_deterministic():
    a = {"b": 1, "a": 2}
    assert packet_hash(a) == packet_hash({"a": 2, "b": 1})
    assert len(packet_hash(a)) == 64
