import importlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _generator():
    return importlib.import_module("scripts.generate_sample_data")


def test_build_is_deterministic():
    g = _generator()
    payload1 = g.build()
    payload2 = g.build()
    assert json.dumps(payload1, sort_keys=True) == json.dumps(payload2, sort_keys=True)


def test_committed_sample_matches_generator():
    committed = ROOT / "data" / "sample" / "sample_trade.json"
    assert committed.exists(), "run scripts/generate_sample_data.py and commit its output"
    g = _generator()
    regenerated = g.build()
    assert json.loads(committed.read_text()) == regenerated


def test_sample_has_disclaimer_and_records():
    g = _generator()
    payload = g.build()
    assert "SYNTHETIC" in payload["disclaimer"].upper()
    assert len(payload["records"]) > 1000
