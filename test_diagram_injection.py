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


def _svg_with(body: str) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">{body}</svg>'


def _write_diagram(tmp_path, name: str, svg: str):
    d = tmp_path / "assets" / "diagrams"
    d.mkdir(parents=True)
    (d / f"{name}.svg").write_text(svg, encoding="utf-8")
    return name


def test_allowlist_blocks_script_tag(monkeypatch, tmp_path):
    """禁止タグ script は注入中止（spec §3.2 allowlist fail-closed）."""
    name = _write_diagram(tmp_path, "evil", _svg_with('<script>alert(1)</script>'))
    monkeypatch.chdir(tmp_path)
    html = convert.enhance_html(f'<p>::: diagram {name}</p>')
    assert 'story-diagram-blocked' in html
    assert '<script' not in html


def test_allowlist_blocks_smil_animation(monkeypatch, tmp_path):
    """SMIL（animate/set）も注入中止（GLM-L2採用・denylist regexの盲点）."""
    name = _write_diagram(tmp_path, "smil", _svg_with('<animate attributeName="x" to="10"/>'))
    monkeypatch.chdir(tmp_path)
    html = convert.enhance_html(f'<p>::: diagram {name}</p>')
    assert 'story-diagram-blocked' in html


def test_allowlist_blocks_entity_bypass_onload(monkeypatch, tmp_path):
    """エンティティ回避（&#111;nload）も注入中止（GLM-L2採用）."""
    name = _write_diagram(tmp_path, "ent", '<svg viewBox="0 0 10 10">&#111;nload=1</svg>')
    monkeypatch.chdir(tmp_path)
    html = convert.enhance_html(f'<p>::: diagram {name}</p>')
    assert 'story-diagram-blocked' in html


def test_allowlist_blocks_forbidden_object_tag(monkeypatch, tmp_path):
    """許可リスト外タグ（foreignObject/image/use）も注入中止（r2・MiniMax r3採用）."""
    name = _write_diagram(tmp_path, "fo", _svg_with('<foreignObject>x</foreignObject>'))
    monkeypatch.chdir(tmp_path)
    html = convert.enhance_html(f'<p>::: diagram {name}</p>')
    assert 'story-diagram-blocked' in html


def test_allowlist_blocks_style_attr(monkeypatch, tmp_path):
    """style属性は全面拒否（r2改訂）."""
    name = _write_diagram(
        tmp_path, "st",
        _svg_with('<rect style="fill:url(http://evil)" x="0" y="0" width="1" height="1"/>'))
    monkeypatch.chdir(tmp_path)
    html = convert.enhance_html(f'<p>::: diagram {name}</p>')
    assert 'story-diagram-blocked' in html


def test_allowlist_passes_valid_diagram_svg(monkeypatch, tmp_path):
    """066話と同構成の正当SVGは通過（sketchy filter・CSS変数・text等を含む）."""
    name = _write_diagram(
        tmp_path, "ok",
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 580" role="img" '
        'aria-labelledby="ok-title"><title id="ok-title">t</title><desc id="ok-desc">d</desc>'
        '<defs><filter id="sketchy"><feTurbulence type="fractalNoise" baseFrequency="0.02" '
        'numOctaves="2" seed="7"/><feDisplacementMap in="SourceGraphic" scale="1.2"/></filter></defs>'
        '<rect width="10" height="10" fill="var(--bg-card)"/><g filter="url(#sketchy)">'
        '<circle cx="5" cy="5" r="3" fill="var(--accent)"/></g>'
        '<text x="5" y="5" font-family="Noto Sans JP">日本語</text></svg>')
    monkeypatch.chdir(tmp_path)
    html = convert.enhance_html(f'<p>::: diagram {name}</p>')
    assert 'story-diagram-blocked' not in html
    assert '<figure class="story-diagram">' in html
    assert 'figcaption' in html
