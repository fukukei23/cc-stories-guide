#!/usr/bin/env python3
"""check_story_public.py — 物語原稿の公開チェック（denylist走査・spec v2 §5）.

使い方: python3 check_story_public.py <story.md> --denylist security-denylist.yaml
終了: 0=通過 / 2=denylistヒット（マスク・削除してから再実行）
"""
import argparse
import pathlib
import re
import sys

import yaml


def main() -> int:
    """denylist走査を実行し、ヒット時は終了コード2で差戻す."""
    ap = argparse.ArgumentParser()
    ap.add_argument("story")
    ap.add_argument("--denylist", default="security-denylist.yaml")
    args = ap.parse_args()
    cfg = yaml.safe_load(pathlib.Path(args.denylist).read_text())
    text = pathlib.Path(args.story).read_text()
    whitelist = cfg.get("whitelist", [])
    hits = []
    for p in cfg.get("patterns", []):
        for m in re.finditer(p["regex"], text):
            if any(w in text[max(0, m.start() - 30):m.end() + 30] for w in whitelist):
                continue
            hits.append((p["name"], m.group(0)))
    if not hits:
        print("OK: denylist該当なし")
        return 0
    for name, frag in hits:
        print(f"[HIT] {name}: {frag[:40]}...", file=sys.stderr)
    print(f"差戻し: {len(hits)}件をマスク・削除してから再実行してください", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
