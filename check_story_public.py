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

from convert import check_svg_allowlist


def scan_diagram_svgs(story_md_path: pathlib.Path) -> list:
    """story内の ::: diagram で参照されるSVGを走査し許可リスト違反を検出（spec §5①・r2二層防御）.

    SVGパスは cwd 相対（convert.py の inject_diagram と同一基準・repo ルートから実行する運用）.
    """
    found = []
    text = story_md_path.read_text(encoding="utf-8")
    for m in re.finditer(r":::\s*diagram\s+(\S+)", text):
        svg = pathlib.Path("assets") / "diagrams" / f"{m.group(1)}.svg"
        if not svg.is_file():
            continue
        violation = check_svg_allowlist(svg.read_text(encoding="utf-8"))
        if violation:
            found.append(f"{svg.name}: {violation}")
    return found


def find_forbidden_svg_tags_in_html(html: str) -> list:
    """公開HTML内の story-diagram figure から禁止タグ/属性を検出（r2改訂・二層防御）."""
    found = []
    for m in re.finditer(r'<figure class="story-diagram">(.*?)</figure>', html, re.DOTALL):
        violation = check_svg_allowlist(m.group(1))
        if violation:
            found.append(violation)
    return found


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
            if any(w in m.group(0) for w in whitelist):
                continue
            hits.append((p["name"], m.group(0)))
    if hits:
        for name, frag in hits:
            print(f"[HIT] {name}: {frag[:40]}...", file=sys.stderr)
        print(f"差戻し: {len(hits)}件をマスク・削除してから再実行してください", file=sys.stderr)
        return 2

    svg_violations = scan_diagram_svgs(pathlib.Path(args.story))
    if svg_violations:
        for v in svg_violations:
            print(f"NG: SVG allowlist違反: {v}", file=sys.stderr)
        print("差戻し: 上記SVGを修正してから再実行してください", file=sys.stderr)
        return 2

    print("OK: denylist該当なし")
    return 0


if __name__ == "__main__":
    sys.exit(main())
