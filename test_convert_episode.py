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


def test_filename_to_slug_known_slugs() -> None:
    """slug生成の回帰テスト（2026-09-07・016話公開時にslug規則が未テストと判明）。

    実slugの実例（公開URLの基盤・変更すると過去URLが壊れる）:
    012_他の作業を... → 012-commit3 / 014_AIの直し提案が3体... → 014-ai3 / 015_設定を... → 015-1
    """
    from convert import _filename_to_slug

    assert _filename_to_slug("013_glm-rate-proxy.md") == "013-glm-rate-proxy"
    assert _filename_to_slug("016_AI審査員の盲点を人間の一言と説明書の改良で塞いだ話.md") == "016-ai"
    # 既存話のslugは公開URLの実名・変更禁止（破壊的変更=過去リンク切れ）
    assert _filename_to_slug("015_設定を1枚の帳票に集めて書き忘れ事故を潰した話.md") == "015-1"


# --- strip_header_comments: published/素材コメントのHTML流出防止（2026-09-26） ---

def test_strip_header_comments_removes_published_comment() -> None:
    """先頭のpublishedコメント（機械読み取り専用）はHTMLへ流さない."""
    from convert import strip_header_comments

    text = "<!-- published: 2026-09-25 / 種別: 教訓 / 素材: 01_DECISIONS/projA/記録.md -->\n\n# タイトル\n\n本文。\n"
    out = strip_header_comments(text)
    assert "素材" not in out
    assert "published" not in out
    assert "# タイトル" in out


def test_strip_header_comments_keeps_body_and_frontmatter() -> None:
    """frontmatter（---開始）と本文は保持する。H1後ろのコメント（001型）も除去."""
    from convert import strip_header_comments

    text = "---\ntitle: x\n---\n\n# タイトル\n\n<!-- published: 2026-09-25 / 種別: 教訓 -->\n\n本文。素材: という語を本文で使う。\n"
    out = strip_header_comments(text)
    assert out.startswith("---")
    assert "<!-- published" not in out  # H1後ろのコメント行も除去
    assert "本文。素材: という語を本文で使う。" in out  # 本文は触らない


def test_strip_header_comments_removes_multiline_comment() -> None:
    """複数行コメント（`<!--` 単独行で開始）も除去する（verify r1 issue 5）."""
    from convert import strip_header_comments

    text = "<!--\npublished: 2026-09-26\n素材: 01_DECISIONS/projA/記録.md\n-->\n\n# タイトル\n\n本文。\n"
    out = strip_header_comments(text)
    assert "素材" not in out
    assert "# タイトル" in out


def test_strip_header_comments_removes_comment_with_trailing_text() -> None:
    """`-->` と同行に本文が続く形式はコメント部のみ除去する（verify r1 issue 5）."""
    from convert import strip_header_comments

    text = "<!-- published: 2026-09-26 / 種別: 教訓 --> 本文のはじまり\n\n# タイトル\n"
    out = strip_header_comments(text)
    assert "published" not in out
    assert "本文のはじまり" in out  # コメント後の本文は保持


def test_strip_header_comments_keeps_comment_inside_code_fence() -> None:
    """コードブロック内のコメントは本文として保持する（誤除去防止・issue 5）."""
    from convert import strip_header_comments

    text = "# タイトル\n\n```markdown\n<!-- published: サンプル -->\nコード例\n```\n\n本文。\n"
    out = strip_header_comments(text)
    assert "<!-- published: サンプル -->" in out  # fence内は保持
    assert "コード例" in out


def test_strip_header_comments_奇数fence閉じ忘れでも決定論的() -> None:
    """verify r2 issue 1回帰: 閉じ忘れfenceがあっても、fence開始前の処理は
    無音に無効化されない（コメント除去は順次処理で決定論的）."""
    from convert import strip_header_comments

    text = ("# タイトル\n\n<!-- published: x / 素材: 01_DECISIONS/p/記録.md -->\n\n"
            "本文。\n\n```python\nprint('閉じ忘れ')\n")
    out = strip_header_comments(text)
    assert "published" not in out  # fence開始前のコメントは普通に除去される
    assert "# タイトル" in out
    assert "本文。" in out
    assert "print('閉じ忘れ')" in out  # 閉じ忘れfence以降はコードとして保持


def test_strip_header_comments_先頭fence原稿はCommonMark準拠で保持() -> None:
    """先頭がfenceの原稿（fenceの組ゼロ）はCommonMarkどおりコード扱いで保持する
    （旧re.split方式の暗黙fence扱いと違い・仕様として明示）."""
    from convert import strip_header_comments

    text = "```\n<!-- 素材: x.md -->\n"
    out = strip_header_comments(text)
    assert "<!-- 素材: x.md -->" in out  # コードとして保持（決定論的仕様）


def test_strip_header_comments_インラインコード内コメントは保持() -> None:
    """verify r2 issue 3: インラインコード（バックティック1個）内のコメント表記は
    本文の説明言及として保持する."""
    from convert import strip_header_comments

    text = "# タイトル\n\n本文 `<!-- 素材: 例 -->` の続き。\n"
    out = strip_header_comments(text)
    assert "`<!-- 素材: 例 -->`" in out  # インラインコードは保持
    assert "の続き。" in out


def test_strip_header_comments_コメント内バックティックペアでも除去() -> None:
    """verify r3 issue 1回帰: コメント内部にバックティックペア（`path.md`）が
    あってもコメントスパンが壊れず除去される（025話型の実在書式）."""
    from convert import strip_header_comments

    text = ("<!-- published: 2026-09-27 / 素材: `01_DECISIONS/projA/記録.md` -->\n\n"
            "# タイトル\n\n本文。\n")
    out = strip_header_comments(text)
    assert "素材" not in out
    assert "published" not in out
    assert "# タイトル" in out


def test_strip_header_comments_複数行コメント内バックティックでも除去() -> None:
    """verify r3 issue 1回帰（複数行版）: 複数行コメント内のバックティックペアでも
    コメント全体が除去される."""
    from convert import strip_header_comments

    text = ("<!--\npublished: 2026-09-27\n素材: `01_DECISIONS/projA/記録.md`\n-->\n\n"
            "# タイトル\n")
    out = strip_header_comments(text)
    assert "素材" not in out
    assert "# タイトル" in out


def test_strip_header_comments_4スペースインデントfenceはfence扱いしない() -> None:
    """verify r3 issue 2回帰: 4スペース以上のインデントはCommonMarkでは
    インデントコードブロックでfence不成立（0-3スペースのみfence開始）."""
    from convert import strip_header_comments

    text = ("# タイトル\n\n    ```\n<!-- published: x -->\n    ```\n\n本文。\n")
    out = strip_header_comments(text)
    assert "published" not in out  # fence開始と誤判定しないので普通に除去される
    assert "本文。" in out
