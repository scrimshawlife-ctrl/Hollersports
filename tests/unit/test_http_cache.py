import json
from pathlib import Path

from hollersports.sources.http_cache import cached_get_json


def test_cached_get_json_hits_disk(tmp_path: Path, monkeypatch):
    calls = {"n": 0}

    def fake_urlopen(req, timeout=20.0):  # noqa: ARG001
        calls["n"] += 1

        class Resp:
            def read(self):
                return json.dumps({"ok": True, "n": calls["n"]}).encode()

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return Resp()

    monkeypatch.setattr("hollersports.sources.http_cache.urlopen", fake_urlopen)
    url = "https://example.test/scoreboard"
    a = cached_get_json(url, cache_dir=tmp_path, ttl_seconds=600)
    b = cached_get_json(url, cache_dir=tmp_path, ttl_seconds=600)
    assert a == b
    assert calls["n"] == 1
