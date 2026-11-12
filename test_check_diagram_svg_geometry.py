"""幾何検査（getBBox交差判定・はみ出し・Contrast）のテスト."""

import pathlib

import check_diagram_svg_geometry as geo

REPO = pathlib.Path(__file__).resolve().parent


def test_066_svg_has_no_overlap():
    """既存066話SVGで重なり0（回帰・066話の品质を保つ）."""
    result = geo.check_geometry(REPO / "assets" / "diagrams" / "066-4.svg")
    assert result.overlaps == [], f"066話で重なり検出: {result.overlaps}"


def test_066_svg_has_no_out_of_bounds():
    """066話SVGはパネル外はみ出し0."""
    result = geo.check_geometry(REPO / "assets" / "diagrams" / "066-4.svg")
    assert result.out_of_bounds == [], f"066話ではみ出し検出: {result.out_of_bounds}"


def test_overlapping_texts_are_detected(tmp_path):
    """重なったtext要素は交差判定で検出される（欠陥注入の基盤）."""
    svg = """<svg viewBox="0 0 200 100" xmlns="http://www.w3.org/2000/svg">
<text x="10" y="30" font-size="14">AAAA</text>
<text x="12" y="32" font-size="14">BBBB</text>
</svg>"""
    p = tmp_path / "overlap.svg"
    p.write_text(svg, encoding="utf-8")
    result = geo.check_geometry(p)
    assert result.overlaps, "重なりが検出されなかった"


def test_out_of_bounds_text_is_detected(tmp_path):
    """viewBox外にはみ出したtextは検出される."""
    svg = """<svg viewBox="0 0 100 50" xmlns="http://www.w3.org/2000/svg">
<text x="150" y="30" font-size="14">はみ出し</text>
</svg>"""
    p = tmp_path / "oob.svg"
    p.write_text(svg, encoding="utf-8")
    result = geo.check_geometry(p)
    assert result.out_of_bounds, "はみ出しが検出されなかった"


def test_contrast_ratio_is_computed():
    """Contrast比が計算される（WCAG式）."""
    assert abs(geo.contrast_ratio("#000000", "#ffffff") - 21.0) < 0.01
    assert geo.contrast_ratio("#ffffff", "#ffffff") == 1.0


def test_css_variable_color_is_contrast_checked_with_fallback():
    """CSS変数（var(--text)）はフォールバック値で判定する."""
    result = geo.check_contrast_pairs([("var(--text)", "#1a1a1a")])
    assert result.failures == [], f"コントラスト不足: {result.failures}"


def test_transform_is_taken_into_account_for_out_of_bounds(tmp_path):
    """祖先gのtransformでviewBox外へ出たtextは検出される.

    getBBox() はローカル座標を返すため、transformを無視すると
    画面外のはみ出しを見逃する（convert.pyのallowlistはg[transform]を許可）。
    """
    svg = """<svg viewBox="0 0 200 100" xmlns="http://www.w3.org/2000/svg">
<g transform="translate(300,0)"><text x="10" y="30" font-size="14">AAAA</text></g>
</svg>"""
    p = tmp_path / "transform.svg"
    p.write_text(svg, encoding="utf-8")
    result = geo.check_geometry(p)
    assert result.out_of_bounds, "transform考慮のないはみ出し見落とし"


def test_transform_is_taken_into_account_for_overlap(tmp_path):
    """祖先gのtransformを考慮した2つのtextの重なりが検出される."""
    svg = """<svg viewBox="0 0 200 100" xmlns="http://www.w3.org/2000/svg">
<g transform="translate(50,50)"><text x="10" y="30" font-size="14">AAAA</text></g>
<g transform="translate(52,52)"><text x="10" y="30" font-size="14">BBBB</text></g>
</svg>"""
    p = tmp_path / "transform_overlap.svg"
    p.write_text(svg, encoding="utf-8")
    result = geo.check_geometry(p)
    assert result.overlaps, "transform考慮のない重なり見落とし"


def test_missing_viewbox_raises_value_error(tmp_path):
    """viewBox欠落はValueError（静かに0件で通さない）."""
    svg = """<svg xmlns="http://www.w3.org/2000/svg">
<text x="10" y="30" font-size="14">AAAA</text>
</svg>"""
    p = tmp_path / "novb.svg"
    p.write_text(svg, encoding="utf-8")
    try:
        geo.check_geometry(p)
    except ValueError:
        return
    raise AssertionError("viewBox欠落でValueErrorが送出されなかった")


def test_svg_contrast_detects_low_contrast_pair(tmp_path):
    """SVGのテキストと背景shapeのコントラスト不足を検出する.

    白文字（#ffffff）を薄い背景（#fffff0）に置くとコントラスト比が閾値未満になる。
    """
    svg = """<svg viewBox="0 0 200 100" xmlns="http://www.w3.org/2000/svg">
<rect x="0" y="0" width="200" height="100" fill="#fffff0"/>
<text x="20" y="40" font-size="14" fill="#ffffff">AAAA</text>
</svg>"""
    p = tmp_path / "lowcontrast.svg"
    p.write_text(svg, encoding="utf-8")
    result = geo.check_svg_contrast(p, theme="dark")
    assert result.failures, "コントラスト不足が検出されなかった"
    assert result.checked >= 1, "判定数が0"


def test_svg_contrast_passes_for_readable_pair(tmp_path):
    """十分なコントラストのSVGは失敗0（誤検出の防止）."""
    svg = """<svg viewBox="0 0 200 100" xmlns="http://www.w3.org/2000/svg">
<rect x="0" y="0" width="200" height="100" fill="#162032"/>
<text x="20" y="40" font-size="14" fill="#e2e8f0">AAAA</text>
</svg>"""
    p = tmp_path / "okcontrast.svg"
    p.write_text(svg, encoding="utf-8")
    result = geo.check_svg_contrast(p, theme="dark")
    assert result.failures == [], f"誤検出: {result.failures}"


def test_svg_contrast_falls_back_to_page_background(tmp_path):
    """shapeで囲まれていないtext（脚注）はページ背景で判定される.

    066話の脚注はshapeの外にあり、ページ背景（var(--bg)）に乗る。
    判定対象から外すと検出漏れになるため、フォールバックで必ず判定する。
    """
    svg = """<svg viewBox="0 0 200 100" xmlns="http://www.w3.org/2000/svg">
<text x="20" y="40" font-size="14" fill="var(--text-secondary)">脚注</text>
</svg>"""
    p = tmp_path / "footnote.svg"
    p.write_text(svg, encoding="utf-8")
    result = geo.check_svg_contrast(p, theme="dark")
    assert result.checked == 1, f"ページ背景フォールバックで判定されない: {result.summary()}"
