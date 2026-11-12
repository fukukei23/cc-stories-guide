"""欠陥注入テスト（spec §12・検出率100%が昇格条件）."""

import pathlib

import check_diagram_svg as cds
import check_diagram_svg_geometry as geo

REPO = pathlib.Path(__file__).resolve().parent
DEFECTS = REPO / "assets" / "diagrams" / "_defects"


def test_defect_overlap_is_detected():
    """欠陥1: テキスト重なり → ⑤geometryで検出."""
    result = geo.check_geometry(DEFECTS / "defect_overlap.svg")
    assert result.overlaps, "重なり欠陥が検出されなかった"


def test_defect_out_of_bounds_is_detected():
    """欠陥2: 文字切れ → ⑤geometryで検出."""
    result = geo.check_geometry(DEFECTS / "defect_out_of_bounds.svg")
    assert result.out_of_bounds, "はみ出し欠陥が検出されなかった"


def test_defect_low_contrast_is_detected():
    """欠陥3: コントラスト不足 → ⑤staticで検出."""
    result = cds.check_svg_text(
        (DEFECTS / "defect_low_contrast.svg").read_text(encoding="utf-8")
    )
    assert result.errors or result.warnings, "低コントラスト欠陥が検出されなかった"


def test_defect_missing_title_is_detected():
    """欠陥5: title欠落 → ⑤staticで検出."""
    result = cds.check_svg_text(
        (DEFECTS / "defect_missing_title.svg").read_text(encoding="utf-8")
    )
    assert any("title" in e for e in result.errors), "title欠落が検出されなかった"


def test_defect_too_many_nodes_is_detected():
    """欠陥6: 構成ノード数超過 → ⑤staticで検出."""
    result = cds.check_svg_text(
        (DEFECTS / "defect_too_many_nodes.svg").read_text(encoding="utf-8")
    )
    assert any("ノード数" in e for e in result.errors), f"検出されなかった: {result.errors}"


def test_defect_missing_svg_produces_placeholder():
    """欠陥4: 図の欠落 → convert.pyがプレースホルダを出す."""
    import convert
    html = convert.enhance_html('<p>::: diagram not_exist_slug_for_defect_test</p>')
    assert 'story-diagram-pending' in html


def test_all_six_defect_types_detected():
    """検出率100%の検証（分母6・分子6）."""
    detected = 0
    total = 6
    r1 = geo.check_geometry(DEFECTS / "defect_overlap.svg")
    detected += 1 if r1.overlaps else 0
    r2 = geo.check_geometry(DEFECTS / "defect_out_of_bounds.svg")
    detected += 1 if r2.out_of_bounds else 0
    r3 = cds.check_svg_text((DEFECTS / "defect_low_contrast.svg").read_text(encoding="utf-8"))
    detected += 1 if (r3.errors or r3.warnings) else 0
    import convert
    detected += 1 if 'story-diagram-pending' in convert.enhance_html(
        '<p>::: diagram not_exist_slug_for_defect_test</p>') else 0
    r5 = cds.check_svg_text((DEFECTS / "defect_missing_title.svg").read_text(encoding="utf-8"))
    detected += 1 if any("title" in e for e in r5.errors) else 0
    r6 = cds.check_svg_text((DEFECTS / "defect_too_many_nodes.svg").read_text(encoding="utf-8"))
    detected += 1 if any("ノード数" in e for e in r6.errors) else 0
    assert detected == total, f"検出率 {detected}/{total} = 100%要件を満たさない"
