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
from generate_story_candidates import (  # noqa: E402
    load_episode_materials,
    load_used_sources,
    main,
    same_day_run,
)


def _write_episode(source_dir, name: str, material: str | None) -> None:
    """tmpにepisode原稿fixtureを作る（素材コメント付き・2026-09-25実害対応）."""
    os.makedirs(source_dir, exist_ok=True)
    comment = f"<!-- published: 2026-09-25 / 種別: 教訓 / 素材: {material} -->\n" if material else "<!-- published: 2026-09-25 / 種別: 教訓 -->\n"
    (source_dir / name).write_text(comment + "\n# テスト話\n\n本文。\n", encoding="utf-8")


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


# ---------------------------------------------------------------------------
# episode素材コメント突合（残余防御・2026-09-25実害対応）
# ---------------------------------------------------------------------------


def test_load_episode_materials_素材コメントから相対パスを収集(tmp_path):
    """episode原稿の `素材:` コメントから物語化済み素材パスを収集できること."""
    _write_episode(tmp_path / "source", "041_テスト話.md", "01_DECISIONS/projA/2026-01-01_テスト記録.md")
    used = load_episode_materials(str(tmp_path / "source"))
    assert used == {"01_DECISIONS/projA/2026-01-01_テスト記録.md"}


def test_load_episode_materials_複数素材は両方収集(tmp_path):
    """複数 `素材:` フィールドは両方収集する（1話が複数記録から成立する場合）."""
    d = tmp_path / "source"
    os.makedirs(d, exist_ok=True)
    (d / "042_テスト話.md").write_text(
        "<!-- published: 2026-09-25 / 種別: 教訓 / 素材: 01_DECISIONS/projA/記録1.md / 素材: 01_DECISIONS/projA/記録2.md -->\n\n# テスト話\n",
        encoding="utf-8")
    used = load_episode_materials(str(d))
    assert used == {"01_DECISIONS/projA/記録1.md", "01_DECISIONS/projA/記録2.md"}


def test_load_episode_materials_素材コメント無し原稿と索引は無視(tmp_path):
    """素材コメント無し原稿・index.md（素材欄無し）は何も収集しない."""
    d = tmp_path / "source"
    _write_episode(d, "041_テスト話.md", None)
    (d / "index.md").write_text("# 索引\n", encoding="utf-8")
    assert load_episode_materials(str(d)) == set()


def test_load_episode_materials_ディレクトリ無しは警告付き空集合(tmp_path, capsys):
    """source/不在は無音の空集合でなくstderr警告を出す（防御の無音無効化防止・issue 2）."""
    assert load_episode_materials(str(tmp_path / "ない")) == set()
    assert "WARN" in capsys.readouterr().err


def test_load_episode_materials_本文の素材行は採集しない(tmp_path):
    """fail条件回帰（verify r1 issue 1・025型）: 本文内の `- 素材:` 行（技術サマリー
    の箇条書き・バックティック付き）は採集せず、コメント内のみ採集する."""
    d = tmp_path / "source"
    _write_episode(d, "041_テスト話.md", "01_DECISIONS/projA/記録1.md")
    # 025型: 本文（detailsサマリー内）にバックティック付き素材行がある原稿を追記
    (d / "042_本文素材行型.md").write_text(
        "<!-- published: 2026-09-26 / 種別: 設計議論 / 素材: 01_DECISIONS/projB/記録2.md -->\n\n"
        "# テスト話\n\n<details><summary>▶ 技術的にどうなってるか</summary>\n\n"
        "- 素材: `01_DECISIONS/projC/本文からは採集されるべきでない.md`（615行）\n\n</details>\n",
        encoding="utf-8")
    used = load_episode_materials(str(d))
    assert "01_DECISIONS/projA/記録1.md" in used
    assert "01_DECISIONS/projB/記録2.md" in used
    assert "01_DECISIONS/projC/本文からは採集されるべきでない.md" not in used


def test_load_episode_materials_複数行コメントも採集(tmp_path):
    """`<!--` 単独行で開始する複数行コメント内の素材も採集する（issue 1の書式網羅）."""
    d = tmp_path / "source"
    os.makedirs(d, exist_ok=True)
    (d / "043_複数行コメント型.md").write_text(
        "<!--\npublished: 2026-09-26\n素材: 01_DECISIONS/projA/複数行.md\n-->\n\n# テスト\n",
        encoding="utf-8")
    used = load_episode_materials(str(d))
    assert used == {"01_DECISIONS/projA/複数行.md"}


def test_load_episode_materials_fence内のコメント例は採集しない(tmp_path):
    """verify r2 issue 2回帰: コードブロック内のコメント例（説明用の引用）は
    採集しない（convert側のfence保持方針と逆方向に不整合にならないように）."""
    d = tmp_path / "source"
    os.makedirs(d, exist_ok=True)
    (d / "044_コード例引用型.md").write_text(
        "<!-- published: 2026-09-27 / 種別: 教訓 / 素材: 01_DECISIONS/projA/本物.md -->\n\n"
        "# テスト\n\n```markdown\n<!-- 素材: 01_DECISIONS/projC/コード例なので除外されない.md -->\n```\n",
        encoding="utf-8")
    used = load_episode_materials(str(d))
    assert used == {"01_DECISIONS/projA/本物.md"}


def test_load_episode_materials_コメント内バックティック付きパスを正規化(tmp_path):
    """verify r3 issue 1関連: コメント内の `素材: \`path.md\`` 記法（025話型）も
    バックティックを除去して正しいパスで採集する（壊れたパスを作らない）."""
    d = tmp_path / "source"
    os.makedirs(d, exist_ok=True)
    (d / "045_バックティック付きコメント型.md").write_text(
        "<!-- published: 2026-09-27 / 素材: `01_DECISIONS/projA/記録.md` -->\n\n# テスト\n",
        encoding="utf-8")
    used = load_episode_materials(str(d))
    assert used == {"01_DECISIONS/projA/記録.md"}


def test_load_episode_materials_インラインコード内コメントは採集しない(tmp_path):
    """verify r4 issue 1回帰: 本文に説明引用しただけのインラインコード内コメントは
    採集しない（正当な素材が過剰排除される実害の防止）."""
    d = tmp_path / "source"
    os.makedirs(d, exist_ok=True)
    (d / "046_インライン引用型.md").write_text(
        "# テスト\n\n本文で `` `<!-- 素材: 01_DECISIONS/projC/説明引用のみ.md -->` ``\nと書いただけ。\n",
        encoding="utf-8")
    assert load_episode_materials(str(d)) == set()


def test_load_episode_materials_実在しない素材パスはWARN(tmp_path, capsys):
    """ssot_rootを渡した時、実在しない素材パスはstderr警告（書式逸脱の無音ミスマッチ防止・issue 3）."""
    d = tmp_path / "source"
    _write_episode(d, "041_テスト話.md", "01_DECISIONS/projA/実在しない.md")
    used = load_episode_materials(str(d), ssot_root=str(tmp_path))
    assert used == {"01_DECISIONS/projA/実在しない.md"}  # 収集はされる（排除は保守側に倒す）
    err = capsys.readouterr().err  # readouterrはバッファ消費型のため1回のみ取得
    assert "WARN" in err
    assert "実在しない" in err


def test_main_episode素材記録で同一素材を排除(tmp_path, capsys):
    """fail条件回帰（2026-09-25実害）: judgment-logにsource欄が無くても、episode原稿の
    素材コメント突合で同一素材の2話目候補を排除できること."""
    log = _write_ssot_and_log(tmp_path, None)  # judgment-logにsource欄なし
    _write_episode(tmp_path / "source", "041_テスト話.md", "01_DECISIONS/projA/2026-01-01_テスト記録.md")
    out = tmp_path / "story-candidates.yaml"
    rc = main(["--ssot", str(tmp_path), "--log", str(log), "--out", str(out)])
    assert rc == 0
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    sources = [c["source"] for c in data["candidates"]]
    assert "01_DECISIONS/projA/2026-01-01_テスト記録.md" not in sources
    assert "01_DECISIONS/judgment-log.yaml" not in str(sources)
    assert "01_DECISIONS/projB/2026-01-01_テスト記録.md" in sources  # 未物語化は残る
    assert "排除" in capsys.readouterr().out


def test_main_素材記録なしepisodeは過剰排除しない(tmp_path):
    """episode原稿に素材コメントが無ければ排除に使わない（過剰排除防止）."""
    log = _write_ssot_and_log(tmp_path, None)
    _write_episode(tmp_path / "source", "041_テスト話.md", None)
    rc = main(["--ssot", str(tmp_path), "--log", str(log), "--out", str(tmp_path / "story-candidates.yaml")])
    assert rc == 0
    data = yaml.safe_load((tmp_path / "story-candidates.yaml").read_text(encoding="utf-8"))
    assert len(data["candidates"]) == 2  # projA/projB両方残る


def test_main_素材コメントで同一素材は排除され候補外パスは残る(tmp_path):
    """素材コメントで排除されるのは同一素材（projA）のみ・別パス（projB）は残る
    （旧名「候補外パスは影響しない」はfixtureが候補内パスの排除を検証しており
    名前と内容が不一致だったため改名・verify r1 issue 4）."""
    log = _write_ssot_and_log(tmp_path, None)
    _write_episode(tmp_path / "source", "041_テスト話.md", "01_DECISIONS/projA/2026-01-01_テスト記録.md")
    out = tmp_path / "story-candidates.yaml"
    rc = main(["--ssot", str(tmp_path), "--log", str(log), "--out", str(out)])
    assert rc == 0
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    # 素材コメントで排除されるのはprojAのみ・projB（別パス）は残る
    assert [c["source"] for c in data["candidates"]] == ["01_DECISIONS/projB/2026-01-01_テスト記録.md"]


def test_load_episode_materials_読み失敗原稿は無視し他は採集(tmp_path, capsys):
    """self-inspect疑義2: 読み失敗原稿は無視（fail-open局部化）し他の原稿の防御は止めない."""
    d = tmp_path / "source"
    os.makedirs(d, exist_ok=True)
    _write_episode(d, "041_正常話.md", "01_DECISIONS/projA/記録1.md")
    broken = d / "042_壊れ話.md"
    broken.write_bytes(b"\xff\xfe\x00invalid-utf8")  # 不正バイト列
    used = load_episode_materials(str(d), ssot_root=str(tmp_path))
    assert "01_DECISIONS/projA/記録1.md" in used  # 正常原稿は採集される


def test_fence_util_閉じfenceは同種かつ同長以上のみ(tmp_path):
    """self-inspect疑義3: 4バックティックで開いたfenceは3バックティックでは閉じない.
    （CommonMark準拠・convert側とgenerate側で共通のsplit_fenced_partsを使用）."""
    from fence_util import split_fenced_parts

    text = "本文\n````\nコード\n```\nまだコード\n````\n\n<!-- published: x -->\n後続本文\n"
    parts = split_fenced_parts(text)
    fence_parts = [p for is_fence, p in parts if is_fence]
    # 閉じ忘れ区間（````〜まだコード）は1つのfence part・3バックティックでは閉じない
    assert any("まだコード" in p for p in fence_parts)
    # 閉じた後の本文コメントは非fence領域にある
    non_fence = "".join(p for is_fence, p in parts if not is_fence)
    assert "後続本文" in non_fence


def test_fence_util_チルダfence対応():
    """self-inspect疑義3: チルダ（~~~）fenceもバックティックと同様に扱う."""
    from fence_util import split_fenced_parts

    text = "本文\n~~~\n<!-- 素材: x -->\n~~~\n<!-- published: y -->\n"
    parts = split_fenced_parts(text)
    fence_parts = "".join(p for is_fence, p in parts if is_fence)
    non_fence = "".join(p for is_fence, p in parts if not is_fence)
    assert "素材: x" in fence_parts   # fence内は保持
    assert "published: y" in non_fence  # fence外は通常処理


def test_fence_util_1_3スペースインデントfenceは有効():
    """self-inspect疑義3: 1-3スペースのインデントfenceはCommonMarkどおり有効."""
    from fence_util import split_fenced_parts

    for indent in (" ", "  ", "   "):
        text = f"{indent}```\nコード\n{indent}```\n後続\n"
        parts = split_fenced_parts(text)
        fence_parts = [p for is_fence, p in parts if is_fence]
        assert any("コード" in p for p in fence_parts), f"indent={indent!r} でfence判定されない"
