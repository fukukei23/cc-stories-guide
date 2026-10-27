#!/usr/bin/env python3
"""CC Stories: source/*.md → docs/llms.txt + docs/llms-full.txt 生成（llmstxt.org仕様）.

convert.py の build_chapter_map() を流用するため、章の追加・タイトル変更は
convert.py 実行後に本スクリプトを再実行すれば llms 側も追従する。
"""

from pathlib import Path

from convert import OUTPUT_DIR, SOURCE_DIR, build_chapter_map

BASE_URL = "https://fukukei23.github.io/cc-stories-guide"
SITE_TITLE = "CC Stories — 作業の物語集"
SITE_DESC = (
    "CC（Claude Code）と一緒に作業した記録を「専門用語なしの物語」と"
    "「技術的にどう作ったか」のペアで残す物語集"
)


def main() -> None:
    """llms.txt（目次）と llms-full.txt（全話全文）を docs/ に生成する。"""
    chapters = build_chapter_map()
    entries: list[str] = []
    full_parts: list[str] = []
    for filename in sorted(chapters):
        meta = chapters[filename]
        url = f"{BASE_URL}/chapters/{meta['slug']}.html"
        entries.append(f"- [{meta['title']}]({url}): {meta['desc']}")
        src = Path(SOURCE_DIR) / filename
        body = src.read_text(encoding="utf-8")
        full_parts.append(f"<!-- {meta['title']} / {url} -->\n\n{body}\n\n---\n")

    llms = f"# {SITE_TITLE}\n\n> {SITE_DESC}\n\n## Stories\n\n" + "\n".join(entries) + "\n"
    (Path(OUTPUT_DIR) / "llms.txt").write_text(llms, encoding="utf-8")

    full = f"# {SITE_TITLE}（全文版）\n\n> {SITE_DESC}\n\n" + "\n".join(full_parts)
    (Path(OUTPUT_DIR) / "llms-full.txt").write_text(full, encoding="utf-8")
    print(f"OK: llms.txt ({len(entries)} entries) + llms-full.txt → {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
