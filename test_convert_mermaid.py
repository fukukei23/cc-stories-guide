"""convert.py enhance_htmlのmermaidルール検証（013話図解対応）"""
from convert import enhance_html


def test_language_mermaid_becomes_mermaid_block() -> None:
    src = '<pre><code class="language-mermaid">flowchart TB\n    A --> B</code></pre>'
    out = enhance_html(src)
    assert '<pre class="mermaid">' in out
    assert "language-mermaid" not in out
    assert "flowchart TB" in out


def test_normal_code_block_untouched() -> None:
    src = '<pre><code class="language-python">print(1)</code></pre>'
    out = enhance_html(src)
    assert '<pre class="mermaid">' not in out
    assert 'class="language-python"' in out


def test_mermaid_escapes_preserved() -> None:
    """markdown-itのエスケープ（-&gt;等）は壊さずそのまま残す（browserがtextContentで復元）"""
    src = '<pre><code class="language-mermaid">A --&gt; B</code></pre>'
    out = enhance_html(src)
    assert '<pre class="mermaid">A --&gt; B</pre>' in out
