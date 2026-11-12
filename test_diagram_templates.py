"""型A/Bテンプレートのテスト（spec §4.2・§4.3）."""

import pathlib

import check_diagram_svg as cds
from check_diagram_svg import ET

REPO = pathlib.Path(__file__).resolve().parent
TEMPLATES = REPO / "assets" / "diagrams" / "_templates"


def test_type_a_template_exists_and_viewbox():
    """型AテンプレートのviewBoxは960x580（spec §4.2）."""
    p = TEMPLATES / "type_a.svg"
    assert p.is_file(), "型Aテンプレートが存在しない"
    root = ET.fromstring(p.read_text(encoding="utf-8"))
    assert root.get("viewBox") == "0 0 960 580"


def test_type_b_template_exists_and_viewbox():
    """型BテンプレートのviewBoxは960x420（spec §4.3）."""
    p = TEMPLATES / "type_b.svg"
    assert p.is_file(), "型Bテンプレートが存在しない"
    root = ET.fromstring(p.read_text(encoding="utf-8"))
    assert root.get("viewBox") == "0 0 960 420"


def test_templates_pass_static_checks():
    """テンプレートは静的検査を通過する（title/desc/aria/viewBox）."""
    for name, expected in (("type_a.svg", (960, 580)), ("type_b.svg", (960, 420))):
        result = cds.check_svg_text(
            (TEMPLATES / name).read_text(encoding="utf-8"), expected
        )
        assert result.errors == [], f"{name} のエラー: {result.errors}"


def test_templates_have_sketchy_filter():
    """sketchyフィルタを含む（spec §4.2・手描きスタイル）."""
    for name in ("type_a.svg", "type_b.svg"):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        assert 'id="sketchy"' in text, f"{name} にsketchyフィルタがない"


def test_templates_use_css_variables():
    """CSS変数を使う（ダーク/ライト自動切替・spec §4.4）."""
    for name in ("type_a.svg", "type_b.svg"):
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        assert "var(--" in text, f"{name} がCSS変数を使っていない"
