#!/usr/bin/env python3
"""test_generate_story_candidates.py — 重複排除・同日skip・flock排他のテスト（2026-09-18 P1修正+r3レビュー採用分）.

fail条件（バックログ事前固定）への対応:
- ①既に物語化済みのsourceを最上位候補として出力しないこと（排除されること）
- ③同日2回発火で2回目がskip（EXIT=3）されること
- r3採用: flock排他で同時発火時も高々1プロセスのみ生成・破損yamlは安全側skip
"""
from __future__ import annotations

import datetime
import os
import sys

import yaml

sys.path.insert(0, os.path.dirname(__file__))
from generate_story_candidates import load_used_sources, main, same_day_run  # noqa: E402


def _write_ssot_and_log(tmp_path, judged_source: str | None, file_name: str = "099_テスト話.md"):
    """tmpにSSOT風fixture（記録1件+judgment-log）を作る."""
    proj_a = tmp_path / "01_DECISIONS" / "projA"
    proj_b = tmp_path / "01_DECISIONS" / "projB"
    proj_a.mkdir(parents=True)
    proj_b.mkdir(parents=True)
    today = datetime.date.today().isoformat()
    body = f"---\nproject: projA\ndate: {today}\n---\n\n# テスト記録\n\n実装した。設計した。新設した。機構を導入した。\n"
    (proj_a / "2026-01-01_テスト記録.md").write_text(body, encoding="utf-8")
    # 別プロジェクト同名ファイル（basename衝突検証用）
    (proj_b / "2026-01-01_テスト記録.md").write_text(body.replace("projA", "projB"), encoding="utf-8")
    entry = {"date": today, "type": "新仕様", "reason": "テスト", "confidence": "高",
             "episode": "099", "file": file_name}
    if judged_source is not None:
        entry["source"] = judged_source
    log = tmp_path / "judgment-log.yaml"
    log.write_text(yaml.safe_dump([entry], allow_unicode=True, sort_keys=False), encoding="utf-8")
    return log


def test_load_used_sources_新形式のsourceを収集(tmp_path):
    log = _write_ssot_and_log(tmp_path, "01_DECISIONS/projA/2026-01-01_テスト記録.md")
    used = load_used_sources(str(log))
    assert used == {"01_DECISIONS/projA/2026-01-01_テスト記録.md"}


def test_load_used_sources_旧形式_entryは無視(tmp_path):
    log = _write_ssot_and_log(tmp_path, None)
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
    assert used == {"01_DECISIONS/claude-code/2026-07-12_ssot-record再設計.md",
                    "01_DECISIONS/x-automation/2026-07-02_X自動投稿戦略.md"}


def test_load_used_sources_空dictは空集合(tmp_path):
    log = tmp_path / "judgment-log.yaml"
    log.write_text("judgments:\nentries:\n", encoding="utf-8")
    assert load_used_sources(str(log)) == set()


def test_same_day_run_当日ならTrue(tmp_path):
    out = tmp_path / "story-candidates.yaml"
    out.write_text(yaml.safe_dump({"generated_at": datetime.datetime.now().isoformat(timespec="seconds"), "candidates": []}), encoding="utf-8")
    assert same_day_run(str(out)) is True


def test_same_day_run_昨日ならFalse(tmp_path):
    out = tmp_path / "story-candidates.yaml"
    yesterday = (datetime.datetime.now() - datetime.timedelta(days=1)).isoformat(timespec="seconds")
    out.write_text(yaml.safe_dump({"generated_at": yesterday, "candidates": []}), encoding="utf-8")
    assert same_day_run(str(out)) is False


def test_same_day_run_ファイル無しはFalse(tmp_path):
    assert same_day_run(str(tmp_path / "ない.yaml")) is False


def test_same_day_run_破損yaml_mtime当日なら安全側skip(tmp_path, capsys):
    """r3レビュー採用: yamlが壊れていてもmtimeが当日ならskip扱い（fail-open防止）."""
    out = tmp_path / "story-candidates.yaml"
    out.write_text("not: valid: yaml: :: !!\n  - [broken\n", encoding="utf-8")  # 即時書込でmtime=当日
    rc = same_day_run(str(out))
    assert rc is True
    assert "安全側skip" in capsys.readouterr().err


def test_main_物語化済みsourceを候補から排除(tmp_path, capsys):
    log = _write_ssot_and_log(tmp_path, "01_DECISIONS/projA/2026-01-01_テスト記録.md")
    out = tmp_path / "story-candidates.yaml"
    rc = main(["--ssot", str(tmp_path), "--log", str(log), "--out", str(out)])
    assert rc == 0
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    # projAの同名ファイルは排除、projBの同名ファイルは未物語化として残る
    sources = [c["source"] for c in data["candidates"]]
    assert "01_DECISIONS/projA/2026-01-01_テスト記録.md" not in sources
    assert "01_DECISIONS/projB/2026-01-01_テスト記録.md" in sources
    assert "排除" in capsys.readouterr().out


def test_main_未物語化sourceは残る(tmp_path):
    log = _write_ssot_and_log(tmp_path, "01_DECISIONS/projA/別の記録.md")
    out = tmp_path / "story-candidates.yaml"
    rc = main(["--ssot", str(tmp_path), "--log", str(log), "--out", str(out)])
    assert rc == 0
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert len(data["candidates"]) == 2  # projA/projB両方残る


def test_main_同日再発火はEXIT3でskip(tmp_path, capsys):
    log = _write_ssot_and_log(tmp_path, "01_DECISIONS/projA/別の記録.md")
    out = tmp_path / "story-candidates.yaml"
    out.write_text("# header\n" + yaml.safe_dump({"generated_at": datetime.datetime.now().isoformat(timespec="seconds"), "candidates": []}), encoding="utf-8")
    before = out.read_text(encoding="utf-8")
    rc = main(["--ssot", str(tmp_path), "--log", str(log), "--out", str(out)])
    assert rc == 3
    assert out.read_text(encoding="utf-8") == before  # 上書きしない
    assert "SKIP" in capsys.readouterr().out


def test_main_ロック競合はEXIT3でskip(tmp_path):
    """r3レビュー採用: flockで別プロセス実行中はEXIT3でskip."""
    log = _write_ssot_and_log(tmp_path, "01_DECISIONS/projA/別の記録.md")
    out = tmp_path / "story-candidates.yaml"
    lock_path = str(out) + ".lock"
    # ロックを外部プロセス保持
    import fcntl
    holder = open(lock_path, "w")
    try:
        fcntl.flock(holder, fcntl.LOCK_EX | fcntl.LOCK_NB)
        rc = main(["--ssot", str(tmp_path), "--log", str(log), "--out", str(out)])
        assert rc == 3
    finally:
        fcntl.flock(holder, fcntl.LOCK_UN)
        holder.close()


def test_main_未来日付は弾く(tmp_path):
    """r3レビュー採用: 未来日付の素材は除外."""
    log = _write_ssot_and_log(tmp_path, "01_DECISIONS/projA/別の記録.md")
    proj_a = tmp_path / "01_DECISIONS" / "projA"
    future = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    (proj_a / "2099-01-01_未来記録.md").write_text(f"---\nproject: projA\ndate: {future}\n---\n\n実装した。", encoding="utf-8")
    out = tmp_path / "story-candidates.yaml"
    rc = main(["--ssot", str(tmp_path), "--log", str(log), "--out", str(out)])
    assert rc == 0
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    sources = [c["source"] for c in data["candidates"]]
    assert not any("未来記録" in s for s in sources)
