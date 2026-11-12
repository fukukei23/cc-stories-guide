#!/usr/bin/env python3
"""図解SVGの前段自動検証（spec §5⑤・2026-11-10_story図解全話展開-design.md）.

静的検査（このファイル）と幾何検査（check_diagram_svg_geometry.py・Task 2）を分離し、
静的検査はブラウザ非依存で単体テスト可能にする。

検査内容（spec §5⑤「前段自動検証」の静的検査部分）:
  - SVGのXML構文がwell-formedか
  - viewBoxの有無・形式・呼び出し側指定型との整合
  - title/desc要素の存在（spec §4.4アクセシビリティ必須）
  - aria-labelledbyの参照先IDが実在するか
  - 複雑性バジェット（1図9ノード以内＝構成パネル枠の数）
  - リテラル色指定（CSS変数で代替を推奨・警告のみ）

CLI: python3 check_diagram_svg.py <svg> [<expected_w> <expected_h>]
終了: 0=エラーなし / 2=エラーあり / 1=usage誤り
出力: 詳細はstderr・1行サマリー(RESULT:)はstdout
"""

from __future__ import annotations

import pathlib
import re
import sys
import xml.etree.ElementTree as StdET

# XXE・billion-laughs対策（defusedxmlがあれば優先・無ければ安全パーサにフォールバック）
try:
    from defusedxml import ElementTree as ET
except ImportError:  # pragma: no cover - 環境依存のフォールバック

    class _SafeET:
        """外部エンティティとDTD展開を拒否するElementTree（defusedxml不在時の代替）."""

        ParseError = StdET.ParseError

        @staticmethod
        def fromstring(text, parser=None):
            if isinstance(text, str):
                text = text.encode("utf-8")
            if b"<!DOCTYPE" in text or b"<!ENTITY" in text:
                raise ValueError("DTD・外部エンティティを含むXMLは拒否します")
            return StdET.fromstring(text)

    ET = _SafeET()  # type: ignore[assignment]

MAX_NODES = 9
# 構成ノード（パネル枠）の判定しきい値: 幅200px以上かつ高さ50px以上のrect
PANEL_MIN_WIDTH = 200
PANEL_MIN_HEIGHT = 50
# リテラル色（#16進/rgb()）のfill/stroke属性を検出する。
# none / url(...) / var(...) はCSS変数・参照なので対象外。
LITERAL_COLOR_RE = re.compile(
    r"""(?:fill|stroke)\s*=\s*["'](?!none["']|url\(|var\()"""
    r"""[^"']*(?:#[0-9a-fA-F]{3,8}|rgba?\([^"']*\))[^"']*["']""",
    re.IGNORECASE,
)


class CheckResult:
    """検査結果（errors=失敗/warnings=要注意）."""

    def __init__(self, errors: list[str], warnings: list[str]):
        self.errors = errors
        self.warnings = warnings

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)

    def summary(self) -> str:
        """機械判定用の1行サマリー."""
        return f"errors={self.error_count} warnings={self.warning_count}"

    def to_dict(self) -> dict:
        return {
            "errors": self.errors,
            "warnings": self.warnings,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
        }


def _localname(tag: str) -> str:
    """名前空間付きタグ名からローカル名を取り出す."""
    return tag.rsplit("}", 1)[-1]


def _numeric_attr(elem: StdET.Element, name: str) -> float | None:
    """数値属性をfloatで返す（不正値・属性なしはNone）."""
    raw = elem.get(name)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _count_panel_nodes(root: StdET.Element) -> int:
    """構成ノード（物語の構成単位＝パネル枠）の数を数える.

    spec §4.4「1図9ノード以内（066話実測で6コマ=6ノードが適合）」のノードは
    物語の構成単位（パネル/段）であって、描画要素の総数ではない。
    1ノード＝1つのパネル枠（幅200px以上かつ高さ50px以上のrect）として判定する。
    """
    count = 0
    for elem in root.iter():
        if _localname(elem.tag) != "rect":
            continue
        width = _numeric_attr(elem, "width")
        height = _numeric_attr(elem, "height")
        if width is None or height is None:
            continue
        if width >= PANEL_MIN_WIDTH and height >= PANEL_MIN_HEIGHT:
            count += 1
    return count


def check_svg_text(svg: str, expected_viewbox: tuple[int, int] | None = None) -> CheckResult:
    """SVG文字列を静的検査する（spec §5⑤の一部）.

    Args:
        svg: 検査対象のSVG文字列.
        expected_viewbox: 期待するviewBoxのサイズ（幅, 高さ）.

    Returns:
        CheckResult: errors=失敗項目・warnings=要注意項目.
    """
    errors: list[str] = []
    warnings: list[str] = []

    try:
        root = ET.fromstring(svg)
    except ET.ParseError as exc:
        return CheckResult([f"SVGのXML構文が不正: {exc}"], [])
    except ValueError as exc:
        return CheckResult([f"SVGの解析が拒否されました: {exc}"], [])

    if _localname(root.tag) != "svg":
        return CheckResult([f"ルート要素がsvgでない: {root.tag}"], [])

    # viewBox整合
    viewbox = root.get("viewBox")
    if not viewbox:
        errors.append("viewBoxが欠落しています")
    else:
        parts = viewbox.split()
        if len(parts) != 4:
            errors.append(f"viewBoxの形式が不正: {viewbox}")
        else:
            try:
                w, h = float(parts[2]), float(parts[3])
            except ValueError:
                errors.append(f"viewBoxの数値が不正: {viewbox}")
            else:
                if expected_viewbox and (w, h) != expected_viewbox:
                    errors.append(
                        f"viewBox不一致: {int(w)}x{int(h)}"
                        f"（期待 {expected_viewbox[0]}x{expected_viewbox[1]}）"
                    )

    # title / desc 必須（spec §4.4アクセシビリティ・figcaption長文代替テキストの前提）
    descendants = list(root.iter())
    if not any(_localname(e.tag) == "title" for e in descendants):
        errors.append("title要素が欠落しています")
    if not any(_localname(e.tag) == "desc" for e in descendants):
        errors.append("desc要素が欠落しています")

    # aria-labelledby の参照整合
    labelledby = root.get("aria-labelledby", "")
    if not labelledby:
        errors.append("aria-labelledbyが欠落しています")
    else:
        existing_ids = {e.get("id") for e in descendants if e.get("id")}
        for ref in labelledby.split():
            if ref not in existing_ids:
                errors.append(f"aria-labelledbyの参照先IDが存在しません: {ref}")

    # 複雑性バジェット（構成ノード＝物語の構成単位・spec §4.4の1図9ノード以内）
    node_count = _count_panel_nodes(root)
    if node_count > MAX_NODES:
        errors.append(
            f"複雑性バジェット超過（ノード数）: "
            f"構成ノード{node_count}個 > {MAX_NODES}個上限"
        )

    # 色指定: CSS変数推奨（リテラルは警告・ダーク/ライト切替が効かない）
    for match in LITERAL_COLOR_RE.finditer(svg):
        warnings.append(f"リテラル色指定（CSS変数推奨）: {match.group(0)}")

    return CheckResult(errors, warnings)


def check_file(
    path: pathlib.Path, expected_viewbox: tuple[int, int] | None = None
) -> CheckResult:
    """SVGファイルを静的検査する.

    Args:
        path: SVGファイルのパス.
        expected_viewbox: 期待するviewBoxのサイズ（幅, 高さ）.

    Returns:
        CheckResult: errors=失敗項目・warnings=要注意項目.
    """
    return check_svg_text(path.read_text(encoding="utf-8"), expected_viewbox)


def main() -> int:
    """CLIエントリポイント.

    Returns:
        int: 0=エラーなし / 2=エラーあり / 1=usage誤り.
    """
    args = sys.argv[1:]
    if not args:
        print(
            "usage: check_diagram_svg.py <svg> [<expected_w> <expected_h>]",
            file=sys.stderr,
        )
        return 1
    expected = None
    if len(args) >= 3:
        try:
            expected = (int(args[1]), int(args[2]))
        except ValueError:
            print("expected_w/expected_h は整数で指定してください", file=sys.stderr)
            return 1
    result = check_file(pathlib.Path(args[0]), expected)
    for err in result.errors:
        print(f"ERROR: {err}", file=sys.stderr)
    for warn in result.warnings:
        print(f"WARN: {warn}", file=sys.stderr)
    print(f"RESULT: {result.summary()}")
    return 2 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
