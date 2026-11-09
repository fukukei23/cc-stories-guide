"""::: diagram ディレクティブ注入のテスト（spec: 2026-11-10_story図解全話展開-design.md）."""

import convert


def test_normalize_html_removes_timestamp():
    """時間依存要素（time属性）を正規化する（spec §3.3・OR1 r2採用）."""
    html = '<meta time="2026-11-10T00:00:00Z"><p>本文</p>'
    assert convert.normalize_html(html) == '<meta time=""><p>本文</p>'


def test_normalize_html_plain_html_unchanged():
    """時間依存要素のないHTMLは無傷."""
    assert convert.normalize_html('<p>本文</p>') == '<p>本文</p>'


def test_diagram_directive_placeholder_when_svg_missing(monkeypatch, tmp_path):
    """SVG不在時はプレースホルダ+fail-warn（spec §3.2）."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "assets" / "diagrams").mkdir(parents=True)
    html = convert.enhance_html('<p>::: diagram test-slug</p>')
    assert 'story-diagram-pending' in html
    assert '図準備中: test-slug' in html
    assert 'svg' not in html.lower()


def test_diagram_directive_no_directive_untouched():
    """ディレクティブなしのHTMLは無傷（既存話の回帰保証）."""
    assert convert.enhance_html('<p>本文</p>') == '<p>本文</p>'
