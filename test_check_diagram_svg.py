"""前段自動検証ツールのテスト（spec §5⑤・2026-11-10_story図解全話展開-design.md）."""

import check_diagram_svg as cds


VALID_SVG = """<svg viewBox="0 0 960 580" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="t d">
<title id="t">タイトル</title>
<desc id="d">説明文</desc>
<g><rect x="10" y="10" width="100" height="50" fill="var(--bg-card)"/>
<text x="20" y="40" font-size="14">本文</text></g>
</svg>"""


def test_valid_svg_passes_all_checks():
    """正常系: 仕様通りのSVGは全検査通過."""
    result = cds.check_svg_text(VALID_SVG)
    assert result.errors == [], f"想定外のエラー: {result.errors}"


def test_missing_title_is_error():
    """title欠落はエラー（spec §4.4アクセシビリティ必須）."""
    svg = VALID_SVG.replace('<title id="t">タイトル</title>', "")
    result = cds.check_svg_text(svg)
    assert any("title" in e for e in result.errors)


def test_missing_desc_is_error():
    """desc欠落はエラー（figcaption長文代替テキストの前提）."""
    svg = VALID_SVG.replace('<desc id="d">説明文</desc>', "")
    result = cds.check_svg_text(svg)
    assert any("desc" in e for e in result.errors)


def test_aria_labelledby_must_reference_existing_ids():
    """aria-labelledbyの参照IDが存在しないとエラー."""
    svg = VALID_SVG.replace('aria-labelledby="t d"', 'aria-labelledby="t missing"')
    result = cds.check_svg_text(svg)
    assert any("aria-labelledby" in e for e in result.errors)


def test_viewbox_mismatch_with_expected_type_is_error():
    """型A用の960x580以外のviewBoxはエラー（型判定は呼び出し側）."""
    svg = VALID_SVG.replace('viewBox="0 0 960 580"', 'viewBox="0 0 960 420"')
    result = cds.check_svg_text(svg, expected_viewbox=(960, 580))
    assert any("viewBox" in e for e in result.errors)


def test_too_many_nodes_is_error():
    """複雑性バジェット9ノード超過はエラー（spec §4.4・構成ノード=パネル数）."""
    panels = "".join(
        f'<rect x="{i*30}" y="0" width="400" height="100" fill="var(--bg-card)"/>'
        for i in range(10)
    )
    svg = VALID_SVG.replace("</g>", panels + "</g>")
    result = cds.check_svg_text(svg)
    assert any("ノード数" in e for e in result.errors), f"エラーなし: {result.errors}"


def test_svg_without_viewbox_is_error():
    """viewBox欠落はエラー."""
    svg = VALID_SVG.replace(' viewBox="0 0 960 580"', "")
    result = cds.check_svg_text(svg)
    assert any("viewBox" in e for e in result.errors)


def test_foreground_color_without_literal_is_warning():
    """fill="var(--text)"はOK（CSS変数）・リテラル#ffffffは警告対象."""
    svg = VALID_SVG.replace('fill="var(--bg-card)"', 'fill="#ffffff"')
    result = cds.check_svg_text(svg)
    assert result.warnings, "リテラル色指定が警告されない"


def test_error_count_summary_is_returned():
    """結果に件数のサマリーが含まれる（機械判定の出力要件）."""
    result = cds.check_svg_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>")
    assert result.error_count >= 1
    assert isinstance(result.summary(), str)


def test_invalid_xml_is_error():
    """XML構文が不正なSVGはエラー1件（他検査に到達しないfatal）."""
    result = cds.check_svg_text("<svg xmlns='http://www.w3.org/2000/svg'><unclosed></svg>")
    assert len(result.errors) == 1, f"エラーが1件であること: {result.errors}"


def test_non_svg_root_is_error():
    """ルート要素がsvgでない場合はエラー."""
    result = cds.check_svg_text(
        "<html xmlns='http://www.w3.org/1999/xhtml'><body/></html>"
    )
    assert any("ルート要素" in e for e in result.errors), f"エラーなし: {result.errors}"


def test_viewbox_with_non_numeric_origin_is_error():
    """viewBoxのmin-x/min-yが数値でない場合はエラー."""
    svg = VALID_SVG.replace('viewBox="0 0 960 580"', 'viewBox="abc def 960 580"')
    result = cds.check_svg_text(svg)
    assert any("viewBox" in e for e in result.errors), f"エラーなし: {result.errors}"
