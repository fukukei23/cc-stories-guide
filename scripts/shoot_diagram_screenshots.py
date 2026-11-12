#!/usr/bin/env python3
"""図解SVGのダーク/ライト両テーマスクショ生成（目視検証用・commitしない）.

check_diagram_svg_geometry.py のCSS変数フォールバック表を流用し、
var(--xxx) を実サイト実測値に置換した上でChromiumで描画・PNG保存する。

CLI: python3 scripts/shoot_diagram_screenshots.py <svg> [<svg> ...]
出力: docs/diagram-shots/<slug>.dark.png / <slug>.light.png
終了: 0=全件出力成功 / 1=usage誤り・出力失敗あり
"""

from __future__ import annotations

import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from check_diagram_svg_geometry import (  # noqa: E402
    CSS_VAR_FALLBACK,
    CSS_VAR_FALLBACK_LIGHT,
    FONT_STACK,
)

_VAR_RE = re.compile(r"var\(\s*(--[a-z0-9-]+)\s*\)")


def _subst(svg_text: str, table: dict) -> str:
    """var(--xxx) をテーブル実測値へ置換する（未知変数は目立つマゼンタに）."""

    def repl(m: re.Match) -> str:
        return table.get(m.group(1), "#ff00ff")

    return _VAR_RE.sub(repl, svg_text)


def main() -> int:
    """CLIエントリポイント.

    Returns:
        int: 0=全件成功 / 1=usage誤り・失敗あり.
    """
    args = sys.argv[1:]
    if not args:
        print(
            "usage: shoot_diagram_screenshots.py <svg> [<svg> ...]",
            file=sys.stderr,
        )
        return 1
    repo = pathlib.Path(__file__).resolve().parent.parent
    out_dir = repo / "docs" / "diagram-shots"
    out_dir.mkdir(parents=True, exist_ok=True)
    failed = 0
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        for arg in args:
            svg_path = pathlib.Path(arg)
            if not svg_path.is_file():
                print(f"{arg}: ERROR: ファイルがありません", file=sys.stderr)
                failed += 1
                continue
            svg_text = svg_path.read_text(encoding="utf-8")
            slug = svg_path.stem
            for theme, table in (
                ("dark", CSS_VAR_FALLBACK),
                ("light", CSS_VAR_FALLBACK_LIGHT),
            ):
                body_bg = "#0c1222" if theme == "dark" else "#f0f4ff"
                body = _subst(svg_text, table)
                html = (
                    "<!DOCTYPE html><html><head><meta charset='utf-8'></head>"
                    f"<body style='margin:0;background:{body_bg};"
                    f"font-family:{FONT_STACK}'>{body}</body></html>"
                )
                page = browser.new_page(
                    viewport={"width": 980, "height": 600}
                )
                try:
                    page.set_content(html)
                    out = out_dir / f"{slug}.{theme}.png"
                    page.screenshot(path=str(out), full_page=True)
                    print(f"{out}")
                except Exception as exc:  # noqa: BLE001
                    print(f"{arg} [{theme}]: ERROR: {exc}", file=sys.stderr)
                    failed += 1
                finally:
                    page.close()
        browser.close()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
