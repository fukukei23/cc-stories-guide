#!/usr/bin/env python3
"""generate_story_candidates.py — SSOT横断スキャンで物語候補をスコア付き生成（spec v2拡張・2026-09-02）.

使い方: python3 generate_story_candidates.py [--ssot ~/projects/obsidian-ssot] [--out story-candidates.yaml]
指標: 種別点(事故解決/新仕様3・反復解消2・運用1) + 素材の厚さ(記録行数) + 減点(機密・キャリア・外向き系は除外)
出力: story-candidates.yaml（score降順・story化済みepisodeは除外）
"""
from __future__ import annotations

import argparse
import datetime
import fcntl
import glob
import os
import re
import sys

import yaml

# 種別判定キーワード（frontmatter/ファイル名/冒頭のスコアリング）
TYPE_RULES = [
    ("事故解決", 3, ["事故", "真因", "バグ", "修復", "解消", "401", "不発", "失敗", "対策", "誤", "穴", "欠陥", "崩壊", "漏"]),
    ("新仕様", 3, ["新設", "構築", "実装", "実装完走", "設計", "導入", "spec", "v3", "機構"]),
    ("反復解消", 2, ["排他", "flock", "冪等", "自動化", "定型", "batch", "毎回", "反復"]),
    ("運用", 1, ["観察", "運用", "点検", "棚卸し", "整理", "更新"]),
]
# 除外（機密・外向き・キャリアは物語化対象外）
EXCLUDE_PATTERNS = [
    r"設定ファイル/", r"SECRETS|シークレット管理台帳|secrets", r"応募|面接|ココナラ|経歴|ポートフォリオ",
    r"settings\.json|scheduled_tasks", r"外向き",
]
MAX_AGE_DAYS = 90  # 古すぎる記録は素材が今の文脈とズレるため対象外（90日）


def classify(title: str, body_head: str) -> tuple[str, int]:
    text = title + "\n" + body_head
    best_type, best_score = "運用", 1
    for tname, tscore, kws in TYPE_RULES:
        hits = sum(1 for k in kws if k in text)
        if hits >= 2 and tscore >= best_score:
            best_type, best_score = tname, tscore
    return best_type, best_score


def thickness(lines: int) -> float:
    """素材の厚さ: 記録が長い=書く材料が多い（0.0〜2.0点）"""
    return min(2.0, lines / 120.0)


def score_entry(path: str, title: str, lines: int, body_head: str) -> float:
    _, t = classify(title, body_head)
    return round(t + thickness(lines), 2)


def load_used_sources(log_path: str) -> set[str]:
    """judgment-log.yamlから物語化済み素材（source正規化相対パス集合）を収集する.

    実データは {judgments: [...], entries: [...]} のdict構造（2026-09-18実測）・
    ベアリスト形式も後方互換で受ける。旧形式エントリ（source 無し）は収集対象外.
    キーはssotルートからの相対パス（basename単独では別プロジェクト同名ファイルを誤排除する・r3レビュー採用）.
    """
    if not os.path.exists(log_path):
        return set()
    with open(log_path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if isinstance(data, dict):
        data = (data.get("judgments") or []) + (data.get("entries") or [])
    if not isinstance(data, list):
        return set()
    used: set[str] = set()
    for e in data:
        if isinstance(e, dict) and e.get("source"):
            used.add(os.path.normpath(str(e["source"])))
    return used


def same_day_run(out_path: str, today: datetime.date | None = None) -> bool:
    """--out先の generated_at が当日なら True（同日再発火skip判定）.

    yaml破損・同時書き込み中の不完全読みでは False（=再生成）に倒すと
    guardが最も必要な瞬間に働かない（r3レビュー採用・fail-open防止）ため、
    mtimeが当日なら安全側skip（True）とする.
    """
    today = today or datetime.date.today()
    try:
        with open(out_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        return False
    except Exception:
        try:
            if datetime.date.fromtimestamp(os.path.getmtime(out_path)) == today:
                print(f"WARN: {out_path} のパース失敗・mtime当日のため安全側skip", file=sys.stderr)
                return True
        except OSError:
            pass
        return False
    if not isinstance(data, dict):
        return False
    gen = data.get("generated_at")
    if not gen:
        return False
    try:
        gen_date = datetime.datetime.fromisoformat(str(gen)).date()
    except ValueError:
        return False
    return gen_date == today


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ssot", default=os.path.expanduser("~/projects/obsidian-ssot"))
    ap.add_argument("--out", default="story-candidates.yaml")
    ap.add_argument("--log", default="judgment-log.yaml")
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args(argv)

    # flock排他（r3レビュー採用・TOCTOU防止: same_day_run判定〜書込までを直列化・2026-09-18）
    lock_path = args.out + ".lock"
    lock_fp = open(lock_path, "w")
    try:
        fcntl.flock(lock_fp, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("SKIP: 別プロセス実行中（flock競合skip・EXIT=3）")
        return 3

    # 同日再発火skip（cron多重発火で同素材を2話公開する事故の防止・2026-09-18）
    try:
        if same_day_run(args.out):
            print("SKIP: 当日生成済み（同日再発火skip・EXIT=3）")
            return 3
    finally:
        fcntl.flock(lock_fp, fcntl.LOCK_UN)
        lock_fp.close()

    used = load_used_sources(args.log)
    root = os.path.join(args.ssot, "01_DECISIONS")
    today = datetime.date.today()  # 単一評価（r3レビュー採用・深夜0時跨ぎの境界バグ防止）
    entries = []
    excluded = 0
    for p in glob.glob(os.path.join(root, "*", "2*.md")):
        base = os.path.basename(p)
        rel = os.path.normpath(os.path.relpath(p, args.ssot))
        if rel in used:
            excluded += 1
            continue  # 既に物語化済み素材（judgment-log source突合・2026-09-18）
        if base.startswith("_INDEX") or "テストは充分" in base or "作業物語ガイド" in base:
            continue  # 既に物語化済み・本仕組み自身は除外
        try:
            text = pathlib_read(p)
        except Exception:
            continue
        m = re.search(r"^date: (\d{4}-\d{2}-\d{2})", text, re.M)
        if not m:
            continue
        d = datetime.date.fromisoformat(m.group(1))
        if d > today or (today - d).days > MAX_AGE_DAYS:  # 未来日も弾く（r3レビュー採用）
            continue
        title = re.sub(r"^\d{4}-\d{2}-\d{2}_", "", base).replace(".md", "")
        if any(re.search(pat, title) or re.search(pat, text[:2000]) for pat in EXCLUDE_PATTERNS):
            continue
        lines = text.count("\n")
        body_head = re.sub(r"^---.*?---", "", text, count=1, flags=re.S)[:3000]
        score = score_entry(p, title, lines, body_head)
        _, ttype = classify(title, body_head)
        proj = os.path.relpath(os.path.dirname(p), root)
        entries.append({
            "date": d.isoformat(), "score": score, "type": ttype, "title": title,
            "project": proj, "source": rel, "lines": lines,
        })
    entries.sort(key=lambda e: (-e["score"], e["date"]))  # 単一ソートに統合（r3レビュー採用）
    entries = entries[: args.limit]
    out = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "rule": "score=種別点+素材厚(行数/120・max2)・除外=機密/キャリア/外向き・90日以内",
        "candidates": entries,
    }
    # アトミック書込（tmp→os.replace・r3レビュー採用）
    tmp_path = args.out + ".tmp"
    with open(tmp_path, "w") as f:
        f.write("# 物語候補リスト（generate_story_candidates.py 自動生成・手動編集は次回生成で上書きされます）\n")
        yaml.safe_dump(out, f, allow_unicode=True, sort_keys=False)
    os.replace(tmp_path, args.out)
    if entries:
        print(f"OK: {len(entries)}件の候補を {args.out} に生成（物語化済み排除{excluded}件・最上位: {entries[0]['score']}点 {entries[0]['title'][:40]}）")
    else:
        print(f"OK: 候補0件（物語化済み排除{excluded}件）")
    return 0


def pathlib_read(p: str) -> str:
    with open(p, encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    sys.exit(main())
