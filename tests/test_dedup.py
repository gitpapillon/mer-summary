"""dedup.load_sent / save_sent 테스트."""

import json
from pathlib import Path

import pytest

from mer_summary.services.dedup import load_sent, save_sent


def test_load_sent_missing_file_returns_empty(tmp_path: Path):
    assert load_sent(tmp_path / "noexist.json") == set()


def test_load_sent_reads_existing(tmp_path: Path):
    f = tmp_path / "state.json"
    f.write_text(
        json.dumps({"sent_log_nos": ["1", "2", "3"]}),
        encoding="utf-8",
    )
    assert load_sent(f) == {"1", "2", "3"}


def test_load_sent_invalid_json_raises(tmp_path: Path):
    f = tmp_path / "bad.json"
    f.write_text("not a json", encoding="utf-8")
    with pytest.raises(RuntimeError, match="파싱 실패"):
        load_sent(f)


def test_load_sent_invalid_shape_raises(tmp_path: Path):
    f = tmp_path / "bad.json"
    f.write_text(json.dumps({"sent_log_nos": "not-a-list"}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="list 아님"):
        load_sent(f)


def test_save_sent_writes_sorted(tmp_path: Path):
    f = tmp_path / "state.json"
    save_sent(f, {"3", "1", "2"})
    data = json.loads(f.read_text(encoding="utf-8"))
    assert data == {"sent_log_nos": ["1", "2", "3"]}


def test_save_sent_creates_parent_dir(tmp_path: Path):
    f = tmp_path / "deep" / "nested" / "state.json"
    save_sent(f, {"a", "b"})
    assert f.exists()


def test_save_then_load_roundtrip(tmp_path: Path):
    f = tmp_path / "rt.json"
    original = {"224291989573", "224291577587", "224290900863"}
    save_sent(f, original)
    assert load_sent(f) == original
