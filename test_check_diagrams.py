"""検査統合CLIのテスト（spec §5①⑤の機械部分）."""

import pathlib

import check_diagrams

REPO = pathlib.Path(__file__).resolve().parent


def test_collect_targets_returns_existing_svgs():
    """assets/diagrams配下のSVG（_templates除く）を対象にする."""
    targets = check_diagrams.collect_targets(REPO / "assets" / "diagrams")
    assert targets, "検査対象SVGが見つからない"
    assert all("_templates" not in str(t) for t in targets)


def test_run_checks_on_066_passes():
    """066話SVGは統合検査を通過する（回帰）."""
    result = check_diagrams.run_checks(
        [REPO / "assets" / "diagrams" / "066-4.svg"], expected_viewbox=(960, 580)
    )
    assert result.errors == [], f"066話が統合検査で失敗: {result.errors}"


def test_run_checks_detects_broken_svg(tmp_path):
    """不正SVGはerrorsに必ず入る."""
    bad = tmp_path / "bad.svg"
    bad.write_text("<svg xmlns='http://www.w3.org/2000/svg'></svg>", encoding="utf-8")
    result = check_diagrams.run_checks([bad], expected_viewbox=(960, 580))
    assert result.errors, "不正SVGが検出されなかった"


def test_result_has_process_level_summary():
    """工程別の内訳を持つ（CC検査ログの保存用）."""
    result = check_diagrams.run_checks(
        [REPO / "assets" / "diagrams" / "066-4.svg"], expected_viewbox=(960, 580)
    )
    assert "static" in result.by_stage
    assert "geometry" in result.by_stage
