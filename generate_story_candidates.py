#!/usr/bin/env python3
"""generate_story_candidates.py — SSOT横断スキャンで物語候補をスコア付き生成（spec v2拡張・2026-09-02）.

使い方: python3 generate_story_candidates.py [--ssot ~/projects/obsidian-ssot] [--out story-candidates.yaml]
指標: 種別点(事故解決/新仕様3・反復解消2・運用1) + 素材の厚さ(記録行数) + 減点(機密・キャリア・外向き系は除外)
出力: story-candidates.yaml（score降順・story化済みepisodeは除外）
"""
from __future__ import annotations

import argparse
import datetime
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ssot", default=os.path.expanduser("~/projects/obsidian-ssot"))
    ap.add_argument("--out", default="story-candidates.yaml")
    ap.add_argument("--limit", type=int, default=40)
    args = ap.parse_args()

    root = os.path.join(args.ssot, "01_DECISIONS")
    cutoff = datetime.date.today() - datetime.timedelta(days=MAX_AGE_DAYS)
    entries = []
    for p in glob.glob(os.path.join(root, "*", "2*.md")):
        base = os.path.basename(p)
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
        if (datetime.date.today() - d).days > MAX_AGE_DAYS or d < cutoff:
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
            "project": proj, "source": os.path.relpath(p, args.ssot), "lines": lines,
        })
    entries.sort(key=lambda e: (-e["score"], e["date"]), reverse=False)
    entries.sort(key=lambda e: -e["score"])
    entries = entries[: args.limit]
    out = {
        "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "rule": "score=種別点+素材厚(行数/120・max2)・除外=機密/キャリア/外向き・90日以内",
        "candidates": entries,
    }
    with open(args.out, "w") as f:
        f.write("# 物語候補リスト（generate_story_candidates.py 自動生成・手動編集は次回生成で上書きされます）\n")
        yaml.safe_dump(out, f, allow_unicode=True, sort_keys=False)
    print(f"OK: {len(entries)}件の候補を {args.out} に生成（最上位: {entries[0]['score']}点 {entries[0]['title'][:40]}）" if entries else "OK: 候補0件")
    return 0


def pathlib_read(p: str) -> str:
    with open(p, encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    sys.exit(main())
