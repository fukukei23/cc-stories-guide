#!/usr/bin/env python3
"""test_generate_story_candidates.py — 重複排除・同日skipのテスト（2026-09-18起票のP1修正分）.

fail条件（バックログ事前固定）への対応:
- ①既に物語化済みのsourceを最上位候補として出力しないこと（排除されること）
- ③同日2回発火で2回目がskip（EXIT=3）されること
"""
from __future__ import annotations

import datetime
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(__file__))
from generate_story_candidates import load_used_sources, main, same_day_run  # noqa: E402


def _write_fixture(tmp_path, source_rel: str, judged_source: str | None):
    """tmpにSSOT風fixture（記録1件+judgment-log）を作る."""
    proj = tmp_path / "01_DECISIONS" / "proj"
    proj.mkdir(parents=True)
    today = datetime.date.today().isoformat()
    (proj / "2026-01-01_テスト記録.md").write_text(
        f"---\nproject: proj\ndate: {today}\n---\n\n# テスト記録\n\n実装した。設計した。新設した。機構を導入した。\n",
        encoding="utf-8",
    )
    entry = {
        "date": today, "type": "新仕様", "reason": "テスト", "confidence": "高",
        "episode": "099", "file": "099_テスト話.md",
    }
    if judged_source is not None:
        entry["source"] = judged_source
    log = tmp_path / "judgment-log.yaml"
    log.write_text(yaml.safe_dump([entry], allow_unicode=True, sort_keys=False), encoding="utf-8")
    return log


def test_load_used_sources_新形式のsourceを収集(tmp_path):
    log = _write_fixture(tmp_path, "x", "01_DECISIONS/proj/2026-01-01_テスト記録.md")
    used = load_used_sources(str(log))
    assert used == {"2026-01-01_テスト記録.md"}


def test_load_used_sources_旧形式_entryは無視(tmp_path):
    log = _write_fixture(tmp_path, "x", None)
    used = load_used_sources(str(log))
    assert used == set()


def test_load_used_sources_ファイル無しは空集合(tmp_path):
    assert load_used_sources(str(tmp_path / "ない.yaml")) == set()


def test_load_used_sources_実データのdict構造に対応(tmp_path):
    """実データ（{judgments, entries}dict構造）でsourceを収集できること（2026-09-18実測の回帰防止）."""
    log = tmp_path / "judgment-log.yaml"
    log.write_text(yaml.safe_dump({
        "judgments": [
            {"episode": "001", "reason": "旧形式・source無し"},
            {"episode": "026", "source": "01_DECISIONS/claude-code/2026-07-12_ssot-record再設計.md"},
        ],
        "entries": [
            {"episode": 28, "source": "01_DECISIONS/x-automation/2026-07-02_X自動投稿戦略.md"},
        ],
    }, allow_unicode=True, sort_keys=False), encoding="utf-8")
    used = load_used_sources(str(log))
    assert used == {"2026-07-12_ssot-record再設計.md", "2026-07-02_X自動投稿戦略.md"}


def test_load_used_sources_空dictは空集合(tmp_path):
    log = tmp_path / "judgment-log.yaml"
    log.write_text("judgments:\nentries:\n", encoding="utf-8")
    assert load_used_sources(str(log)) == set()


def test_same_day_run_当日ならTrue(tmp_path):
    out = tmp_path / "story-candidates.yaml"
    out.write_text(
        yaml.safe_dump({"generated_at": datetime.datetime.now().isoformat(timespec="seconds"), "candidates": []}),
        encoding="utf-8",
    )
    assert same_day_run(str(out)) is True


def test_same_day_run_昨日ならFalse(tmp_path):
    out = tmp_path / "story-candidates.yaml"
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat(timespec="seconds")
    out.write_text(
        yaml.safe_dump({"generated_at": yesterday, "candidates": []}), encoding="utf-8"
    )
    assert same_day_run(str(out)) is False


def test_same_day_run_ファイル無しはFalse(tmp_path):
    assert same_day_run(str(tmp_path / "ない.yaml")) is False


def test_main_物語化済みsourceを候補から排除(tmp_path, capsys):
    log = _write_fixture(tmp_path, "x", "01_DECISIONS/proj/2026-01-01_テスト記録.md")
    out = tmp_path / "story-candidates.yaml"
    rc = main(["--ssot", str(tmp_path), "--log", str(log), "--out", str(out)])
    assert rc == 0
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert data["candidates"] == []  # 唯一の候補が排除される
    assert "排除" in capsys.readouterr().out


def test_main_未物語化sourceは残る(tmp_path):
    log = _write_fixture(tmp_path, "x", "01_DECISIONS/proj/別の記録.md")
    out = tmp_path / "story-candidates.yaml"
    rc = main(["--ssot", str(tmp_path), "--log", str(log), "--out", str(out)])
    assert rc == 0
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert len(data["candidates"]) == 1
    assert data["candidates"][0]["source"].endswith("2026-01-01_テスト記録.md")


def test_main_同日再発火はEXIT3でskip(tmp_path, capsys):
    log = _write_fixture(tmp_path, "x", "01_DECISIONS/proj/別の記録.md")
    out = tmp_path / "story-candidates.yaml"
    out.write_text(
        "# 物語候補リスト\n" + yaml.safe_dump(
            {"generated_at": datetime.datetime.now().isoformat(timespec="seconds"), "candidates": []}
        ),
        encoding="utf-8",
    )
    before = out.read_text(encoding="utf-8")
    rc = main(["--ssot", str(tmp_path), "--log", str(log), "--out", str(out)])
    assert rc == 3
    assert out.read_text(encoding="utf-8") == before  # 上書きしない
    assert "SKIP" in capsys.readouterr().out
