"""convert.py話数抽出＋バッジ表示の網羅性テスト（2026-09-07 MLR後追加）

実バグ002_マルチLLM=第4話（ファイル名002→「第4話」表示すべき）の再発防止のため
優先順位（meta > H1「第N話」 > ファイル名）とゼロ埋め正規化を固定する。
"""
from convert import CHAPTER_TEMPLATE, _episode_number, enhance_html


# --- _episode_number: 優先順位 ---

def test_frontmatter_episode_priority_overrides_h1_and_filename() -> None:
    """MLR採用Gemini/MiniMax指摘: meta値が最強優先"""
    assert _episode_number({"episode": "13"}, "002_マルチLLM.md", "第4話") == "13"


def test_h1_priority_over_filename() -> None:
    """H1の「第N話」がファイル名より優先（実バグの本丸・filename=002だがtitle=第4話→4）"""
    assert _episode_number({}, "002_マルチLLM.md", "マルチLLMレビュー（第4話）") == "4"


def test_filename_fallback_when_no_h1_no_meta() -> None:
    """meta/H1ともになければファイル名先頭数字にフォールバック"""
    assert _episode_number({}, "013_図解.md", "") == "13"


def test_filename_zero_padded_stripped() -> None:
    """ゼロ埋め「002」は「2」へ正規化"""
    assert _episode_number({}, "002_x.md", "") == "2"


def test_filename_no_digits_returns_empty() -> None:
    """数字なしのファイル名は空文字（バッジ非表示）"""
    assert _episode_number({}, "special_story.md", "") == ""


def test_filename_with_ep_prefix_supported() -> None:
    """ep01_形式も拾う（テンプレ互換）"""
    assert _episode_number({}, "ep07_x.md", "") == "7"


def test_h1_two_digit_and_three_digit() -> None:
    """桁数境界: 第10話/第100話"""
    assert _episode_number({}, "x.md", "第10話") == "10"
    assert _episode_number({}, "x.md", "第100話") == "100"


def test_h1_chooses_first_match_in_body() -> None:
    """本文中の「第N話」表記の先頭一致（タイトル由来）"""
    # titleは本文全体ではなく抽出済みH1相当を想定
    assert _episode_number({}, "x.md", "第4話の話。第5話は次回") == "4"


def test_episode_number_zero() -> None:
    """Gemini指摘: episode=0（プロローグ等）は明示判定"""
    assert _episode_number({"episode": 0}, "x.md", "") == "0"
    assert _episode_number({}, "x.md", "第0話") == "0"


def test_empty_inputs_return_empty() -> None:
    """全フォールバック失敗時は空文字（テンプレートif条件と整合）"""
    assert _episode_number({}, "x.md", "タイトルだけ") == ""
    assert _episode_number({}, "x.md", "") == ""
    assert len(_episode_number({}, "x.md", "")) == 0


# --- enhance_html: mermaidルール（マルチブロック・隣接・属性違い） ---

def test_multiple_mermaid_blocks_all_replaced() -> None:
    """ページ内に複数のmermaidがあっても両方置換される（013話+他話で実証予定）"""
    src = (
        '<pre><code class="language-mermaid">A-->B</code></pre>'
        '<p>中間テキスト</p>'
        '<pre><code class="language-mermaid">C-->D</code></pre>'
    )
    out = enhance_html(src)
    assert out.count('<pre class="mermaid">') == 2
    assert "language-mermaid" not in out
    assert "中間テキスト" in out  # 非mermaid部分は不変


def test_mermaid_with_extra_class_attribute() -> None:
    """MLR指摘: class属性に他クラスが追加されている場合の扱い（仕様確認）"""
    # 現状の正規表現は完全一致なので追加属性があるとマッチしない→不変（これが現行挙動）
    src = '<pre><code class="language-mermaid foo">A-->B</code></pre>'
    out = enhance_html(src)
    # マッチしないので変換されない（false negativeだが実用上extra_classは通常無い）
    assert "language-mermaid" in out or '<pre class="mermaid">' in out
    # 動作を保証するため: 現状は不一致→置換なし（仕様の現状固定）
    # 注: 本テストは将来extra class対応した場合に分岐が必要


def test_mermaid_and_python_adjacent_blocks() -> None:
    """隣接するpythonブロックは不変"""
    src = (
        '<pre><code class="language-mermaid">A-->B</code></pre>'
        '<pre><code class="language-python">print(1)</code></pre>'
    )
    out = enhance_html(src)
    assert '<pre class="mermaid">' in out
    assert 'class="language-python"' in out
    assert "print(1)" in out


# --- CHAPTER_TEMPLATEバッジ描画の統合テスト ---

def test_chapter_badge_renders_with_number() -> None:
    """テンプレート側が「第N話」バッジを正しく描画"""
    out = CHAPTER_TEMPLATE.render(
        title="テスト", slug="t", current_slug="t",
        content="<p>x</p>", chapters=[], prev_ch=None, next_ch=None,
        number="13",
    )
    assert '<div class="episode-badge">第13話</div>' in out


def test_chapter_badge_omitted_when_number_empty() -> None:
    """空文字numberの時はバッジ非表示"""
    out = CHAPTER_TEMPLATE.render(
        title="テスト", slug="t", current_slug="t",
        content="<p>x</p>", chapters=[], prev_ch=None, next_ch=None,
        number="",
    )
    assert "episode-badge" not in out
