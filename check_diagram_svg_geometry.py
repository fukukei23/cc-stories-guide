#!/usr/bin/env python3
"""図解SVGの幾何検査（spec §5⑤・Playwright getBBoxによる交差判定・はみ出し・Contrast）.

静的検査（check_diagram_svg.py）と分離した幾何検査。
ChromiumでSVGを実際にレンダリングし、text要素のbounding boxを取得して
  - 交差判定（重なり）
  - viewBox外はみ出し判定
  - コントラスト比計算（WCAG 2.x）
を行う。

座標系について:
  getBBox() は要素のローカル座標を返すため、祖先の transform を無視する。
  祖先 transform 対策として getScreenCTM() の逆行列で
  「textのローカル座標 → root svgのviewBox座標」へ変換してから判定する
  （convert.py のSVG allowlist は g[transform] を許可しているため必要）。

CLI: python3 check_diagram_svg_geometry.py <svg> [<svg> ...] [--contrast]
終了: 0=違反なし / 2=違反あり / 1=usage誤り
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

CONTRAST_THRESHOLD = 4.5

# style.cssの実測値（assets/style.css・2026-11-12実測）
# ライト: L4-L30 / ダーク: L33-L54
# 図解SVGで使用する変数はすべて収録済み（未収録は #000000 にフォールバックする）。
CSS_VAR_FALLBACK = {
    "--bg": "#0c1222",
    "--bg-card": "#162032",
    "--bg-secondary": "#1a2744",
    "--text": "#e2e8f0",
    "--text-secondary": "#94a3b8",
    "--accent": "#818cf8",
    "--accent-bg": "#1e1b4b",
    "--accent-dark": "#a5b4fc",
    "--green": "#4ade80",
    "--green-bg": "#064e3b",
    "--amber": "#fbbf24",
    "--amber-bg": "#451a03",
    "--red": "#f87171",
    "--red-bg": "#450a0a",
    "--blue": "#60a5fa",
    "--blue-bg": "#172554",
    "--border": "#334155",
    "--code-bg": "#0f172a",
    "--code-text": "#e2e8f0",
}

CSS_VAR_FALLBACK_LIGHT = {
    "--bg": "#f0f4ff",
    "--bg-card": "#ffffff",
    "--bg-secondary": "#e8edf5",
    "--text": "#1e293b",
    "--text-secondary": "#64748b",
    "--accent": "#6366f1",
    "--accent-bg": "#eef2ff",
    "--accent-dark": "#4f46e5",
    "--green": "#10b981",
    "--green-bg": "#ecfdf5",
    "--amber": "#f59e0b",
    "--amber-bg": "#fffbeb",
    "--red": "#ef4444",
    "--red-bg": "#fef2f2",
    "--blue": "#3b82f6",
    "--blue-bg": "#eff6ff",
    "--border": "#cbd5e1",
    "--code-bg": "#1e293b",
    "--code-text": "#e2e8f0",
}

_CSS_VAR_RE = re.compile(r"var\(\s*(--[a-z0-9-]+)\s*\)")
_RGB_RE = re.compile(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)")

# 実サイトのフォントスタック（assets/style.css L28）。
# getBBoxはフォントの字幅で変わるため、描画と同じフォントを指定しないと
# 実サイトとは異なる幅で交差判定される。
FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, "
    "'Noto Sans JP', 'Hiragino Sans', sans-serif"
)

# コントラスト判定の失敗時に指摘する色の上限（1ファイルあたりの出力膨胀を防ぐ）
MAX_CONTRAST_REPORTS = 20


class GeometryResult:
    """幾何検査結果."""

    def __init__(
        self,
        overlaps: list[dict],
        out_of_bounds: list[dict],
        text_count: int,
    ):
        self.overlaps = overlaps
        self.out_of_bounds = out_of_bounds
        self.text_count = text_count

    def summary(self) -> str:
        """機械判定用の1行サマリー."""
        return (
            f"texts={self.text_count} overlaps={len(self.overlaps)} "
            f"out_of_bounds={len(self.out_of_bounds)}"
        )

    def to_dict(self) -> dict:
        """機械判定出力用のdictに変換する."""
        return {
            "overlaps": self.overlaps,
            "out_of_bounds": self.out_of_bounds,
            "text_count": self.text_count,
        }


class ContrastResult:
    """コントラスト検査結果."""

    def __init__(self, failures: list[dict], checked: int):
        self.failures = failures
        self.checked = checked

    def summary(self) -> str:
        """機械判定用の1行サマリー."""
        return f"checked={self.checked} failures={len(self.failures)}"

    def to_dict(self) -> dict:
        """機械判定出力用のdictに変換する."""
        return {
            "failures": self.failures,
            "checked": self.checked,
        }


def _rel_luminance(hex_color: str) -> float:
    """WCAG 2.x の相対輝度.

    Args:
        hex_color: #rgb / #rrggbb 形式の色.

    Returns:
        float: 相対輝度（0.0-1.0）.
    """
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    r, g, b = (int(h[i: i + 2], 16) / 255 for i in (0, 2, 4))

    def channel(c: float) -> float:
        """sRGB 8bit値を線形輝度へ変換する."""
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast_ratio(fg: str, bg: str) -> float:
    """前景色と背景色のコントラスト比（WCAG 2.x）.

    Args:
        fg: 前景色（#rgb / #rrggbb）.
        bg: 背景色（#rgb / #rrggbb）.

    Returns:
        float: コントラスト比（1.0-21.0）.
    """
    l1, l2 = _rel_luminance(fg), _rel_luminance(bg)
    if l1 < l2:
        l1, l2 = l2, l1
    return (l1 + 0.05) / (l2 + 0.05)


def resolve_color(value: str, theme: str = "dark") -> str:
    """CSS変数指定・rgb()形式を16進colorspecへ解決する.

    Args:
        value: 色指定文字列（#hex / rgb() / var(--name)）.
        theme: "dark" or "light"（フォールバック表の選択）.

    Returns:
        str: #rrggbb 形式の色. 解決できない場合は "#000000".
    """
    value = (value or "").strip()
    if value.startswith("#"):
        return value
    rgb_match = _RGB_RE.match(value)
    if rgb_match:
        r, g, b = (int(x) for x in rgb_match.groups())
        return f"#{r:02x}{g:02x}{b:02x}"
    match = _CSS_VAR_RE.search(value)
    if match:
        var_name = match.group(1)
        table = CSS_VAR_FALLBACK_LIGHT if theme == "light" else CSS_VAR_FALLBACK
        return table.get(var_name, "#000000")
    return "#000000"


def check_contrast_pairs(
    pairs: list[tuple[str, str]], theme: str = "dark"
) -> ContrastResult:
    """（前景色, 背景色）の組を判定する. 閾値4.5未満は失敗.

    Args:
        pairs: (前景色, 背景色) の組のリスト.
        theme: "dark" or "light"（CSS変数のフォールバック表の選択）.

    Returns:
        ContrastResult: failures=閾値未満の組・checked=判定数.
    """
    failures = []
    for index, (fg, bg) in enumerate(pairs):
        fg_hex = resolve_color(fg, theme)
        bg_hex = resolve_color(bg, theme)
        ratio = contrast_ratio(fg_hex, bg_hex)
        if ratio < CONTRAST_THRESHOLD:
            failures.append(
                {
                    "fg": fg,
                    "bg": bg,
                    "ratio": round(ratio, 2),
                    "threshold": CONTRAST_THRESHOLD,
                    "index": index,
                }
            )
    return ContrastResult(failures, len(pairs))


# 幾何検査用JS。
# getBBox() はローカル座標を返すため、祖先transformを反映した
# AABB（軸平行境界箱）を計算してから判定する。
_GEOMETRY_SCRIPT = r"""
() => {
  const svg = document.querySelector('svg');
  if (!svg) { return {error: 'svg要素が見つかりません'}; }

  const vbAttr = svg.getAttribute('viewBox');
  if (!vbAttr) { return {error: 'viewBoxが欠落しています'}; }
  const vb = vbAttr.trim().split(/[\s,]+/).map(Number);
  if (vb.length !== 4 || vb.some((n) => !isFinite(n))) {
    return {error: 'viewBoxの数値が不正です: ' + vbAttr};
  }
  const minX = vb[0], minY = vb[1], vw = vb[2], vh = vb[3];

  // root svg のユーザー座標（＝viewBox座標）へ変換する逆行列
  const rootCtm = svg.getScreenCTM();
  const inv = rootCtm ? rootCtm.inverse() : null;

  function toRoot(el, x, y) {
    if (!inv) { return {x: x, y: y}; }
    const m = inv.multiply(el.getScreenCTM());
    return {x: m.a * x + m.c * y + m.e, y: m.b * x + m.d * y + m.f};
  }

  // 変換後の軸平行境界箱
  function rootAabb(el) {
    const b = el.getBBox();
    const pts = [[b.x, b.y], [b.x + b.width, b.y],
                 [b.x, b.y + b.height], [b.x + b.width, b.y + b.height]];
    const p = pts.map((pt) => toRoot(el, pt[0], pt[1]));
    const xs = p.map((q) => q.x), ys = p.map((q) => q.y);
    const x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs);
    const y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys);
    return {x: x0, y: y0, w: x1 - x0, h: y1 - y0};
  }

  const texts = Array.from(document.querySelectorAll('svg text'));
  const boxes = texts.map((el) => {
    const b = rootAabb(el);
    return {x: b.x, y: b.y, w: b.w, h: b.h,
            t: (el.textContent || '').slice(0, 30)};
  });

  const overlaps = [];
  for (let a = 0; a < boxes.length; a++) {
    for (let c = a + 1; c < boxes.length; c++) {
      const A = boxes[a], B = boxes[c];
      const ox = Math.min(A.x + A.w, B.x + B.w) - Math.max(A.x, B.x);
      const oy = Math.min(A.y + A.h, B.y + B.h) - Math.max(A.y, B.y);
      if (ox > 0 && oy > 0) {
        overlaps.push({a: A.t, b: B.t,
                       ox: Math.round(ox * 100) / 100,
                       oy: Math.round(oy * 100) / 100});
      }
    }
  }

  const outOfBounds = boxes.filter((b) => b.x < minX || b.y < minY ||
                                            b.x + b.w > minX + vw ||
                                            b.y + b.h > minY + vh);
  return {boxes: boxes, overlaps: overlaps, outOfBounds: outOfBounds,
          vw: vw, vh: vh};
}
"""


# コントラスト検査用JS。
# 各textについて「そのtextの下の最上位の塗りつぶしshape」を見つけ、
# （前景色, 背景色）の組を列挙する。fill はCSS変数aybe hexの生値を保持する。
_CONTRAST_SCRIPT = r"""
() => {
  const svg = document.querySelector('svg');
  if (!svg) { return {error: 'svg要素が見つかりません'}; }

  const rootCtm = svg.getScreenCTM();
  const inv = rootCtm ? rootCtm.inverse() : null;

  function toRoot(el, x, y) {
    if (!inv) { return {x: x, y: y}; }
    const m = inv.multiply(el.getScreenCTM());
    return {x: m.a * x + m.c * y + m.e, y: m.b * x + m.d * y + m.f};
  }

  function rootAabb(el) {
    const b = el.getBBox();
    const pts = [[b.x, b.y], [b.x + b.width, b.y],
                 [b.x, b.y + b.height], [b.x + b.width, b.y + b.height]];
    const p = pts.map((pt) => toRoot(el, pt[0], pt[1]));
    const xs = p.map((q) => q.x), ys = p.map((q) => q.y);
    const x0 = Math.min.apply(null, xs), x1 = Math.max.apply(null, xs);
    const y0 = Math.min.apply(null, ys), y1 = Math.max.apply(null, ys);
    return {x: x0, y: y0, w: x1 - x0, h: y1 - y0};
  }

  // fill はCSS変数aybe hexの生値を保持する（getComputedStyleではvar()が溶けるため）
  function effectiveFill(el) {
    let cur = el;
    while (cur && cur.getAttribute) {
      const f = cur.getAttribute('fill');
      if (f !== null && f !== '') { return f; }
      cur = cur.parentNode;
    }
    return null;
  }

  const SHAPES = 'rect, circle, ellipse, polygon, path';
  const shapes = Array.from(svg.querySelectorAll(SHAPES))
    .filter((el) => {
      const f = effectiveFill(el);
      return f !== null && f !== 'none' && f !== 'transparent';
    })
    .map((el) => ({el: el, fill: effectiveFill(el), aabb: rootAabb(el)}));

  const pairs = [];
  const texts = Array.from(svg.querySelectorAll('svg text'));
  for (const el of texts) {
    const fg = effectiveFill(el);
    if (fg === null || fg === 'none') { continue; }
    const xAttr = parseFloat(el.getAttribute('x'));
    const yAttr = parseFloat(el.getAttribute('y'));
    if (!isFinite(xAttr) || !isFinite(yAttr)) { continue; }
    const anchor = toRoot(el, xAttr, yAttr);
    // アンカー位置を含む最も手前（文書順で後）のshapeを背景とする
    let bg = null;
    for (const s of shapes) {
      const a = s.aabb;
      if (anchor.x >= a.x && anchor.x <= a.x + a.w &&
          anchor.y >= a.y && anchor.y <= a.y + a.h) {
        bg = s.fill;
      }
    }
    // shapeで囲まれていないtext（脚注など）はページ背景（body）に乗る
    if (bg === null) { bg = 'var(--bg)'; }
    pairs.push({fg: fg, bg: bg,
                text: (el.textContent || '').slice(0, 30)});
  }
  return {pairs: pairs};
}
"""


def _render_svg(svg_path: pathlib.Path, script: str) -> dict:
    """Playwright+ChromiumでSVGをレンダリングしてJSスクリプトを実行する.

    Args:
        svg_path: 検査対象のSVGファイルのパス.
        script: ブラウザ内で実行するJS（矢印関数を文字列で渡す）.

    Returns:
        dict: JSスクリプトの戻り値.

    Raises:
        ValueError: SVG要素・viewBoxが不正な場合.
    """
    from playwright.sync_api import sync_playwright

    svg_text = svg_path.read_text(encoding="utf-8")
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'></head>"
        f"<body style='margin:0;font-family:{FONT_STACK}'>{svg_text}</body></html>"
    )
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1400, "height": 1000})
            page.set_content(html)
            data = page.evaluate(script)
        finally:
            browser.close()
    if isinstance(data, dict) and "error" in data:
        raise ValueError(f"{svg_path}: {data['error']}")
    return data


def check_geometry(svg_path: pathlib.Path) -> GeometryResult:
    """Playwright+ChromiumでgetBBoxによる交差判定・はみ出し判定を行う.

    Args:
        svg_path: 検査対象のSVGファイルのパス.

    Returns:
        GeometryResult: overlaps / out_of_bounds / text_count.

    Raises:
        ValueError: SVG要素・viewBoxが不正な場合.
    """
    data = _render_svg(svg_path, _GEOMETRY_SCRIPT)
    return GeometryResult(
        overlaps=data["overlaps"],
        out_of_bounds=[
            {"t": b["t"], "x": b["x"], "y": b["y"], "w": b["w"], "h": b["h"]}
            for b in data["outOfBounds"]
        ],
        text_count=len(data["boxes"]),
    )


def check_svg_contrast(
    svg_path: pathlib.Path, theme: str = "dark"
) -> ContrastResult:
    """SVGのテキストと、その下の背景shapeのコントラストを判定する.

    Args:
        svg_path: 検査対象のSVGファイルのパス.
        theme: "dark" or "light"（CSS変数のフォールバック表の選択）.

    Returns:
        ContrastResult: failures=閾値未満の組・checked=判定数.
    """
    data = _render_svg(svg_path, _CONTRAST_SCRIPT)
    pairs = [(p["fg"], p["bg"]) for p in data["pairs"]]
    result = check_contrast_pairs(pairs, theme=theme)
    # どのテキストで失敗したかを紐づける（indexはpairs内の位置）
    for failure in result.failures:
        pair = data["pairs"][failure["index"]]
        failure["text"] = pair["text"]
    return result


def main() -> int:
    """CLIエントリポイント.

    Returns:
        int: 0=違反なし / 2=違反あり / 1=usage誤り.
    """
    args = sys.argv[1:]
    with_contrast = "--contrast" in args
    files = [a for a in args if not a.startswith("--")]
    if not files:
        print(
            "usage: check_diagram_svg_geometry.py <svg> [<svg> ...] [--contrast]",
            file=sys.stderr,
        )
        return 1
    total_fail = 0
    for arg in files:
        try:
            result = check_geometry(pathlib.Path(arg))
        except (OSError, ValueError) as exc:
            print(f"{arg}: ERROR: {exc}", file=sys.stderr)
            total_fail += 1
            continue
        print(f"{arg}: {result.summary()}")
        for o in result.overlaps:
            print(f"  OVERLAP: '{o['a']}' x '{o['b']}' ox={o['ox']} oy={o['oy']}")
        for b in result.out_of_bounds:
            print(f"  OUT_OF_BOUNDS: '{b['t']}'")
        if result.overlaps or result.out_of_bounds:
            total_fail += 1
        if with_contrast:
            for theme in ("dark", "light"):
                try:
                    cres = check_svg_contrast(pathlib.Path(arg), theme=theme)
                except (OSError, ValueError) as exc:
                    print(f"  CONTRAST({theme}): ERROR: {exc}", file=sys.stderr)
                    total_fail += 1
                    continue
                print(f"  CONTRAST({theme}): {cres.summary()}")
                for f in cres.failures[:MAX_CONTRAST_REPORTS]:
                    print(
                        f"    LOW_CONTRAST: '{f.get('text', '')}' "
                        f"fg={f['fg']} bg={f['bg']} ratio={f['ratio']}"
                    )
                if len(cres.failures) > MAX_CONTRAST_REPORTS:
                    print(
                        f"    ... 他{len(cres.failures) - MAX_CONTRAST_REPORTS}件"
                    )
                if cres.failures:
                    total_fail += 1
    print(json.dumps({"failed_files": total_fail}, ensure_ascii=False))
    return 2 if total_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
