"""check_story_public.py の SVG走査拡張テスト（spec §5①・r2二層防御）."""

import check_story_public as csp


def test_svg_allowlist_violation_detected():
    """check_svg_allowlist 経由で許可リスト外タグを検知."""
    assert csp.check_svg_allowlist('<svg><script>alert(1)</script></svg>') is not None
    assert csp.check_svg_allowlist('<svg><rect/></svg>') is None


def test_public_html_forbidden_tag_detected():
    """公開HTML側の figure内SVGから禁止タグ検出（r2改訂・二層防御）."""
    html = '<figure class="story-diagram"><svg><script>x</script></svg></figure>'
    assert csp.find_forbidden_svg_tags_in_html(html)
    ok = '<figure class="story-diagram"><svg><rect/></svg></figure>'
    assert not csp.find_forbidden_svg_tags_in_html(ok)


def test_scan_diagram_svgs_detects_violation(tmp_path, monkeypatch):
    """story md の ::: diagram 参照先 SVG が違反なら検出."""
    story = tmp_path / "story.md"
    story.write_text("# t\n\n::: diagram evil-slug\n", encoding="utf-8")
    d = tmp_path / "assets" / "diagrams"
    d.mkdir(parents=True)
    (d / "evil-slug.svg").write_text('<svg><script>x</script></svg>', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    found = csp.scan_diagram_svgs(story)
    assert found
    assert "evil-slug.svg" in found[0]


def test_scan_diagram_svgs_passes_clean(tmp_path, monkeypatch):
    story = tmp_path / "story.md"
    story.write_text("# t\n\n::: diagram clean-slug\n", encoding="utf-8")
    d = tmp_path / "assets" / "diagrams"
    d.mkdir(parents=True)
    (d / "clean-slug.svg").write_text('<svg><rect/></svg>', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert not csp.scan_diagram_svgs(story)
