#!/usr/bin/env python3
"""図解SVGの公開前検査（spec §5①⑤の機械部分・統合CLI）.

工程①denylist走査は check_story_public.py が担う（既存・変更しない）。
本CLIは②allowlist（convert.py）・⑤前段自動検証を1コマンドで実行する。

CLI: python3 check_diagrams.py [--viewbox W H] [<svg dir>]
終了: 0=エラーなし / 2=エラーあり / 1=検査対象なし
"""

from __future__ import annotations

import pathlib
import sys

import check_diagram_svg as cds
import check_diagram_svg_geometry as geo
from convert import check_svg_allowlist


class UnifiedResult:
    """統合検査結果."""

    def __init__(self, errors: list[str], warnings: list[str], by_stage: dict):
        self.errors = errors
        self.warnings = warnings
        self.by_stage = by_stage

    def summary(self) -> str:
        """機械判定用の1行サマリー."""
        return f"errors={len(self.errors)} warnings={len(self.warnings)}"

    def to_dict(self) -> dict:
        """機械判定出力用のdictに変換する."""
        return {
            "errors": self.errors,
            "warnings": self.warnings,
            "by_stage": self.by_stage,
        }


def collect_targets(diagrams_dir: pathlib.Path) -> list[pathlib.Path]:
    """検査対象のSVG一覧（_templates配下は除く）.

    Args:
        diagrams_dir: SVGを配置するディレクトリ.

    Returns:
        list[pathlib.Path]: ソート済みのSVGパス一覧.
    """
    if not diagrams_dir.is_dir():
        return []
    # glob("*")は再帰しないため _templates/ 配下は自然に除外される
    return sorted(p for p in diagrams_dir.glob("*.svg") if p.is_file())


def run_checks(
    svg_paths: list[pathlib.Path],
    expected_viewbox: tuple[int, int] | None = None,
    skip_geometry: bool = False,
) -> UnifiedResult:
    """静的検査・allowlist検査・幾何検査を実行する.

    Args:
        svg_paths: 検査対象のSVGファイルのパス一覧.
        expected_viewbox: 期待するviewBoxのサイズ（幅, 高さ）.
        skip_geometry: Trueの場合、幾何検査（ブラウザ描画）を省略する.

    Returns:
        UnifiedResult: errors / warnings / 工程別内訳.
    """
    errors: list[str] = []
    warnings: list[str] = []
    by_stage: dict[str, dict] = {"static": {}, "allowlist": {}, "geometry": {}}

    for path in svg_paths:
        text = path.read_text(encoding="utf-8")

        # 工程②: allowlist（convert.py実装を流用）
        violation = check_svg_allowlist(text)
        by_stage["allowlist"][path.name] = "ok" if not violation else "ng"
        if violation:
            errors.append(f"[allowlist] {path.name}: {violation}")

        # 工程⑤(static): 静的検査
        static = cds.check_svg_text(text, expected_viewbox)
        by_stage["static"][path.name] = "ok" if not static.errors else "ng"
        errors.extend(f"[static] {path.name}: {e}" for e in static.errors)
        warnings.extend(f"[static] {path.name}: {w}" for w in static.warnings)

        # 工程⑤(geometry): getBBox交差判定・はみ出し
        if skip_geometry:
            by_stage["geometry"][path.name] = "skipped"
            continue
        try:
            geom = geo.check_geometry(path)
        except (OSError, ValueError) as exc:
            # SVG要素欠落・viewBox欠落等は検査不能（エラーとして扱う）
            by_stage["geometry"][path.name] = "error"
            errors.append(f"[geometry] {path.name}: 検査失敗 {exc}")
            continue
        by_stage["geometry"][path.name] = (
            "ok" if not geom.overlaps and not geom.out_of_bounds else "ng"
        )
        for o in geom.overlaps:
            errors.append(
                f"[geometry] {path.name}: テキスト重なり '{o['a']}' x '{o['b']}'"
            )
        for b in geom.out_of_bounds:
            errors.append(f"[geometry] {path.name}: パネル外はみ出し '{b['t']}'")

    return UnifiedResult(errors, warnings, by_stage)


def main() -> int:
    """CLIエントリポイント.

    Returns:
        int: 0=エラーなし / 2=エラーあり / 1=検査対象なし.
    """
    args = sys.argv[1:]
    expected = None
    if args[:1] == ["--viewbox"] and len(args) >= 3:
        expected = (int(args[1]), int(args[2]))
        args = args[3:]
    target_dir = pathlib.Path(args[0]) if args else pathlib.Path("assets/diagrams")
    targets = collect_targets(target_dir)
    if not targets:
        print(f"検査対象のSVGがありません: {target_dir}", file=sys.stderr)
        return 1
    result = run_checks(targets, expected)
    for e in result.errors:
        print(f"ERROR: {e}")
    for w in result.warnings:
        print(f"WARN: {w}")
    print(f"RESULT: {result.summary()} files={len(targets)}")
    return 2 if result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
