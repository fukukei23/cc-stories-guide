#!/usr/bin/env python3
"""CC Stories: Markdown → モバイル最適化HTML変換スクリプト."""

import re
import shutil
from pathlib import Path

from jinja2 import Template
from markdown_it import MarkdownIt

# --- 設定 ---

SOURCE_DIR = Path(__file__).parent / "source"
OUTPUT_DIR = Path(__file__).parent / "docs"

# 既存章の手動定義（タイトル・アイコン・説明をカスタマイズしたい場合に記載）
# ここに書かれていないファイルは source/ を自動スキャンして追加される
# storiesは自動スキャン運用のため未定義（フロントマター/H1から title・desc・icon を抽出）
CHAPTER_MAP: dict = {}


# --- 自動スキャン ---

def _filename_to_slug(filename: str) -> str:
    """ファイル名からslugを生成: '13_glm-rate-proxy.md' → '13-glm-rate-proxy'"""
    stem = Path(filename).stem  # 拡張子除去
    # 先頭の数字+区切り文字を抽出: "13_foo" → "13-foo", "00_早見表" → "00-cheatsheet相当"
    # アンダースコアをハイフンに、日本語はASCIIに変換できないのでそのまま残す
    slug = stem.replace("_", "-", 1)  # 最初の _ のみハイフン化
    # 残りの _ もハイフン化
    slug = slug.replace("_", "-")
    # ASCII以外の文字を除去してslugを作る
    ascii_slug = ""
    for ch in slug:
        if ch.isascii():
            ascii_slug += ch.lower()
        elif ch == "-":
            ascii_slug += "-"
    # 連続ハイフン・末尾ハイフンを整理
    ascii_slug = re.sub(r"-+", "-", ascii_slug).strip("-")
    return ascii_slug or slug


def _extract_frontmatter(text: str) -> tuple[dict, str]:
    """YAMLフロントマターを抽出。なければ空dictとテキストをそのまま返す。"""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    fm_text = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")
    meta = {}
    for line in fm_text.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta, body


def _extract_title_from_h1(text: str) -> str:
    """H1ヘッダーからタイトルを抽出。'# 13 GLM Rate Proxy — ...' → 'GLM Rate Proxy'"""
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            # 番号プレフィックスを除去: "13 GLM Rate Proxy" → "GLM Rate Proxy"
            title = re.sub(r"^\d+\s+", "", title)
            # ダッシュ以降の説明を除去: "GLM Rate Proxy — 説明" → "GLM Rate Proxy"
            title = re.split(r"\s+[—–-]\s+", title)[0].strip()
            return title
    return ""


def _extract_desc_from_h1(text: str) -> str:
    """H1ヘッダーのダッシュ以降を説明として抽出。"""
    for line in text.splitlines():
        if line.startswith("# "):
            parts = re.split(r"\s+[—–-]\s+", line[2:].strip(), maxsplit=1)
            if len(parts) > 1:
                return parts[1].strip()
    return ""


def _episode_number(meta: dict, filename: str) -> str:
    """カード表示用の話数を返す。frontmatterの `episode:` を最優先し、
    なければ ep01_*.md 形式のファイル名から抽出。どちらもなければ空文字（ラベル非表示）。"""
    ep = meta.get("episode")
    if ep:
        return ep
    match = re.match(r"ep(\d+)", Path(filename).stem)
    return match.group(1) if match else ""


def build_chapter_map() -> dict:
    """source/ の実ファイルのみからCHAPTER_MAPを構築。
    CHAPTER_MAPのメタデータを実ファイルに適用。実在しないエントリは表示しない(404防止)。"""
    result = {}

    for md_file in sorted(SOURCE_DIR.glob("*.md")):
        filename = md_file.name
        if filename.startswith("_"):
            continue  # _README.md等は除外
        if filename == "index.md":
            # トップページ本文はINDEX_TEMPLATE側で持つため、source/index.mdは読まず章にもしない
            continue

        text = md_file.read_text(encoding="utf-8")
        meta, body = _extract_frontmatter(text)

        if filename in CHAPTER_MAP:
            # CHAPTER_MAPのメタデータを適用(フロントマターがあれば優先)
            base = CHAPTER_MAP[filename]
            result[filename] = {
                "slug": base["slug"],
                "title": meta.get("title") or base["title"],
                "icon": meta.get("icon", base["icon"]),
                "desc": meta.get("card_desc") or meta.get("desc") or base["desc"],
            }
        else:
            title = meta.get("title") or _extract_title_from_h1(text) or Path(filename).stem
            desc = meta.get("card_desc") or meta.get("desc") or _extract_desc_from_h1(text) or title
            icon = meta.get("icon", "📄")
            slug = meta.get("slug") or _filename_to_slug(filename)
            result[filename] = {
                "slug": slug,
                "title": title,
                "icon": icon,
                "desc": desc,
                "episode": _episode_number(meta, filename),
            }
            print(f"AUTO: {filename} → {slug} ({title})")

    return result

# --- HTMLテンプレート ---

CHAPTER_TEMPLATE = Template("""\
<!DOCTYPE html>
<html lang="ja" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} — CC Stories</title>
    <meta name="description" content="CC Stories — 作業の物語集: {{ title }}">
    <meta property="og:title" content="{{ title }} — CC Stories">
    <meta property="og:description" content="{{ title }} — 専門用語なしの物語と技術解説のペア">
    <meta property="og:type" content="article">
    <meta property="og:url" content="https://fukukei23.github.io/cc-stories-guide/chapters/{{ slug }}.html">
    <meta property="og:image" content="https://fukukei23.github.io/cc-stories-guide/assets/ogp.png">
    <meta name="twitter:card" content="summary_large_image">
    <link rel="stylesheet" href="../assets/style.css">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📚</text></svg>">
</head>
<body>
    <header class="site-header">
        <button class="menu-toggle" aria-label="メニュー" id="menuToggle">
            <span></span><span></span><span></span>
        </button>
        <a href="../index.html" class="site-title">📚 CC Stories</a>
        <button class="theme-toggle" id="themeToggle" aria-label="テーマ切替">
            <span class="icon-light">☀️</span>
            <span class="icon-dark">🌙</span>
        </button>
    </header>

    <nav class="sidebar" id="sidebar">
        <div class="sidebar-header">
            <a href="../index.html">🏠 ホーム</a>
        </div>
        {% for ch in chapters %}
        <a href="{{ ch.slug }}.html"
           class="sidebar-link{{ ' active' if ch.slug == current_slug }}">
            <span class="sidebar-icon">{{ ch.icon }}</span>
            {{ ch.title }}
        </a>
        {% endfor %}
    </nav>
    <div class="sidebar-overlay" id="sidebarOverlay"></div>

    <main class="content">
        <div class="chapter-nav-top">
            {% if prev_ch %}
            <a href="{{ prev_ch.slug }}.html" class="nav-prev">← {{ prev_ch.title }}</a>
            {% endif %}
            {% if next_ch %}
            <a href="{{ next_ch.slug }}.html" class="nav-next">{{ next_ch.title }} →</a>
            {% endif %}
        </div>

        <article class="chapter-body">
            {{ content|safe }}
        </article>

        <nav class="chapter-nav-bottom">
            {% if prev_ch %}
            <a href="{{ prev_ch.slug }}.html" class="nav-card prev">
                <span class="nav-label">← 前の章</span>
                <span class="nav-title">{{ prev_ch.icon }} {{ prev_ch.title }}</span>
            </a>
            {% endif %}
            {% if next_ch %}
            <a href="{{ next_ch.slug }}.html" class="nav-card next">
                <span class="nav-label">次の章 →</span>
                <span class="nav-title">{{ next_ch.icon }} {{ next_ch.title }}</span>
            </a>
            {% endif %}
        </nav>
    </main>

    <footer class="site-footer">
        <p>CC Stories — <a href="https://github.com/fukukei23/cc-stories-guide">GitHub</a>
         · <a href="https://fukukei23.github.io/ssot-guide/">SSOT Guide</a>
         · <a href="https://fukukei23.github.io/loop-engineering-guide/">Loop Engineering Guide</a>
         · <a href="https://fukukei23.github.io/guides/">技術ガイド集</a>
         · <a href="https://fukukei23.github.io/">fukukei23</a></p>
    </footer>

    <script src="../assets/script.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
    <script>
        mermaid.initialize({
            startOnLoad: true,
            theme: document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'default',
            themeVariables: { fontSize: '14px' }
        });
    </script>
</body>
</html>
""", autoescape=True)

INDEX_TEMPLATE = Template("""\
<!DOCTYPE html>
<html lang="ja" data-theme="light">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CC Stories — 作業の物語集</title>
    <meta name="description" content="CCと一緒に作業した記録を「専門用語なしの物語」と「技術的にどう作ったか」のペアで残す物語集">
    <meta property="og:title" content="CC Stories — 作業の物語集">
    <meta property="og:description" content="CCと一緒に作業した記録を物語+技術解説のペアで残す">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://fukukei23.github.io/cc-stories-guide/">
    <meta property="og:image" content="https://fukukei23.github.io/cc-stories-guide/assets/ogp.png">
    <meta name="twitter:card" content="summary_large_image">
    <link rel="stylesheet" href="assets/style.css">
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📚</text></svg>">
</head>
<body class="index-page">
    <header class="site-header">
        <span class="site-title">📚 CC Stories</span>
        <button class="theme-toggle" id="themeToggle" aria-label="テーマ切替">
            <span class="icon-light">☀️</span>
            <span class="icon-dark">🌙</span>
        </button>
    </header>

    <main class="content">
        <section class="hero">
            <h1>📚 CC Stories</h1>
            <p>CC（Claude Code）と一緒に作業した記録を、<br>専門用語なしの物語と「技術的にどう作ったか」のペアで残す</p>
        </section>

        {% for cat in categories %}
        <section class="chapter-category">
            <h2 class="chapter-category-heading">{{ cat.name }}</h2>
            <div class="chapter-grid">
                {% for ch in cat.chapters %}
                <a href="chapters/{{ ch.slug }}.html" class="chapter-card">
                    <div class="card-icon">{{ ch.icon }}</div>
                    {% if ch.number %}<div class="card-number">第{{ ch.number }}話</div>{% endif %}
                    <h2 class="card-title">{{ ch.title }}</h2>
                    <p class="card-desc">{{ ch.desc }}</p>
                </a>
                {% endfor %}
            </div>
        </section>
        {% endfor %}

        <section class="features">
            <h2>📖 このサイトの特徴</h2>
            <div class="feature-grid">
                <div class="feature-item">
                    <span class="feature-icon">📖</span>
                    <h3>物語ファースト</h3>
                    <p>専門用語なしで「何をして、何が起きたか」を読める</p>
                </div>
                <div class="feature-item">
                    <span class="feature-icon">🔧</span>
                    <h3>技術解説つき</h3>
                    <p>各話に「▶ 技術的にどう作ったか」の解説を添えている</p>
                </div>
                <div class="feature-item">
                    <span class="feature-icon">📱</span>
                    <h3>モバイル対応</h3>
                    <p>スマホの隙間時間でサクッと1話読める</p>
                </div>
                <div class="feature-item">
                    <span class="feature-icon">🌙</span>
                    <h3>ダークモード</h3>
                    <p>夜の閲覧にも優しいテーマ切替</p>
                </div>
            </div>
        </section>
    </main>

    <footer class="site-footer">
        <p>CC Stories — <a href="https://github.com/fukukei23/cc-stories-guide">GitHub</a>
         · <a href="https://fukukei23.github.io/ssot-guide/">SSOT Guide</a>
         · <a href="https://fukukei23.github.io/loop-engineering-guide/">Loop Engineering Guide</a>
         · <a href="https://fukukei23.github.io/guides/">技術ガイド集</a>
         · <a href="https://fukukei23.github.io/">fukukei23</a></p>
    </footer>

    <script src="assets/script.js"></script>
</body>
</html>
""", autoescape=True)


# --- Markdown → HTML変換 ---

def convert_md_to_html(md_text: str) -> str:
    """MarkdownをHTMLに変換（見出しID記法 {#id} を id 属性に変換）。."""
    md = MarkdownIt("commonmark", {"html": False}).enable("table")
    html = md.render(md_text)
    return _attach_heading_ids(html)


def _attach_heading_ids(html: str) -> str:
    """MarkdownIt が残した {#id} を h1-h6 の id 属性に変換.

    例: <h2>概要 {#overview}</h2> → <h2 id="overview">概要</h2>
    html:False 環境で attrs プラグイン不要の軽量パーサ。
    """
    def _repl(match: "re.Match") -> str:
        level, text, hid = match.group(1), match.group(2), match.group(3)
        return f'<h{level} id="{hid}">{text}</h{level}>'
    return re.sub(
        r'<h([1-6])>(.*?)\s*\{#([^}]+)\}\s*</h\1>',
        _repl,
        html,
    )


def rewrite_links(html: str, chapter_map: dict | None = None) -> str:
    """内部リンクをHTML URLに書き換え."""
    from urllib.parse import quote, unquote

    cmap = chapter_map or CHAPTER_MAP

    for filename, info in cmap.items():
        # [テキスト](XX_YY.md) → XX-yy.html
        html = html.replace(f'href="{filename}', f'href="{info["slug"]}.html')
        # [テキスト](XX_YY.md#anchor) → XX-yy.html#anchor
        html = re.sub(
            rf'href="{re.escape(filename)}#',
            f'href="{info["slug"]}.html#',
            html,
        )

        # URLエンコードされたリンク（例: 11_%E7%8F%BE%E5%A0%B4...）も処理
        encoded_name = quote(filename, safe='')
        if encoded_name != filename:
            html = html.replace(f'href="{encoded_name}', f'href="{info["slug"]}.html')
            html = re.sub(
                rf'href="{re.escape(encoded_name)}#',
                f'href="{info["slug"]}.html#',
                html,
            )

    # 未変換の.mdリンクをすべて処理
    def replace_md_link(match):
        href = match.group(1)
        for filename, info in cmap.items():
            decoded = unquote(href)
            if filename in decoded or filename in href:
                anchor = ""
                if "#" in href:
                    anchor = "#" + href.split("#", 1)[1]
                elif "#" in decoded:
                    anchor = "#" + decoded.split("#", 1)[1]
                return f'href="{info["slug"]}.html{anchor}"'
        return 'href="#"'

    html = re.sub(r'href="([^"]*\.md[^"]*)"', replace_md_link, html)

    # 外部リンク（他リポジトリ内のファイルへの相対リンク）を除去
    html = re.sub(r'href="\.\./[^"]*"', 'href="#"', html)
    html = re.sub(r'href="01_DECISIONS[^"]*"', 'href="#"', html)

    return html


def enhance_html(html: str) -> str:
    """HTMLに装飾を追加（テーブルラップ・コールアウト等）."""
    # テーブルをスクロールラッパーで囲む
    html = re.sub(
        r"(<table[^>]*>.*?</table>)",
        r'<div class="table-wrapper">\1</div>',
        html,
        flags=re.DOTALL,
    )

    # 引用ブロックをコールアウトに変換
    def callout_replace(match):
        content = match.group(1)
        if "注意" in content or "⚠" in content:
            return f'<div class="callout callout-warn"><p>{content}</p></div>'
        if "重要" in content:
            return f'<div class="callout callout-danger"><p>{content}</p></div>'
        if "現場の知見" in content or "💡" in content or "Tip" in content:
            return f'<div class="callout callout-tip"><p>{content}</p></div>'
        return f'<div class="callout callout-info"><p>{content}</p></div>'

    html = re.sub(r"<blockquote>\s*<p>(.*?)</p>\s*</blockquote>", callout_replace, html, flags=re.DOTALL)

    return html


def convert_tldr(html: str) -> str:
    """H1直後の『3行で分かる』blockquote を <aside class="tldr"> に変換.

    平易化（2026-07-03）: 各ページH1直後に置いた `> **3行で分かる**` blockquoteを
    目立つTLDR枠に変換する。enhance_html の単一段落callout変換（<blockquote><p>…</p></blockquote>）
    にマッチしない複数要素blockquoteを対象とするため、enhance_html の後に呼ぶこと。
    H1直後の最初のblockquoteのみ（位置保証）。'3行で分かる' を含まなければ変換しない（後方互換）。
    """
    pattern = re.compile(
        r'(<h1[^>]*>.*?</h1>\s*)(<blockquote>.*?</blockquote>)',
        re.DOTALL,
    )
    m = pattern.search(html)
    if not m:
        return html
    head, block = m.group(1), m.group(2)
    if '3行で分かる' not in block:
        return html
    inner = block[len('<blockquote>'):-len('</blockquote>')]
    converted = head + f'<aside class="tldr">{inner}</aside>'
    return html[:m.start()] + converted + html[m.end():]


# --- トップページのカテゴリ分け ---

# 章番号→カテゴリの境界（番号レンジは閉区間）
# storiesは全話を1カテゴリで表示（番号体系が固定でないため）
INDEX_CATEGORIES = [
    ("📚 話一覧", 0, 9999),
]
INDEX_CATEGORY_FALLBACK = "📚 話一覧"


def group_chapters_by_category(chapters: list) -> list:
    """章番号レンジに基づき、トップページ表示用にカテゴリへグルーピング."""
    buckets = {name: [] for name, _, _ in INDEX_CATEGORIES}
    buckets[INDEX_CATEGORY_FALLBACK] = []

    for ch in chapters:
        number = ch["number"]
        category_name = INDEX_CATEGORY_FALLBACK
        if number.isdigit():
            n = int(number)
            for name, lo, hi in INDEX_CATEGORIES:
                if lo <= n <= hi:
                    category_name = name
                    break
        buckets[category_name].append(ch)

    ordered_names = [name for name, _, _ in INDEX_CATEGORIES] + [INDEX_CATEGORY_FALLBACK]
    # INDEX_CATEGORIESとフォールバックが同名だと重複して2回表示されるため排除
    ordered_names = list(dict.fromkeys(ordered_names))
    return [{"name": name, "chapters": buckets[name]} for name in ordered_names if buckets[name]]


# --- メイン ---

def main():
    # ディレクトリ準備
    chapters_dir = OUTPUT_DIR / "chapters"
    assets_dir = OUTPUT_DIR / "assets"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    assets_dir.mkdir(parents=True, exist_ok=True)

    # 章リストを構築（自動スキャン込み）
    effective_map = build_chapter_map()

    # slug衝突は後勝ち上書きではなく検知して落とす（ chapters/{slug}.html が壊れるため）
    slug_counts: dict[str, int] = {}
    for info in effective_map.values():
        slug_counts[info["slug"]] = slug_counts.get(info["slug"], 0) + 1
    duplicates = {slug for slug, count in slug_counts.items() if count > 1}
    if duplicates:
        raise SystemExit(f"slug重複: {', '.join(sorted(duplicates))}")

    chapters = []
    for filename, info in sorted(effective_map.items()):
        chapters.append({
            "number": info.get("episode", ""),  # 「第N話」ラベル（frontmatter episode 優先）
            "slug": info["slug"],
            "title": info["title"],
            "icon": info["icon"],
            "desc": info["desc"],
            "filename": filename,
        })

    # 各章を変換
    for i, ch in enumerate(chapters):
        src = SOURCE_DIR / ch["filename"]
        if not src.exists():
            print(f"SKIP: {ch['filename']} not found")
            continue

        md_text = src.read_text(encoding="utf-8")
        html_body = convert_md_to_html(md_text)
        html_body = rewrite_links(html_body, effective_map)
        html_body = convert_tldr(html_body)
        html_body = enhance_html(html_body)

        prev_ch = chapters[i - 1] if i > 0 else None
        next_ch = chapters[i + 1] if i < len(chapters) - 1 else None

        full_html = CHAPTER_TEMPLATE.render(
            title=ch["title"],
            slug=ch["slug"],
            current_slug=ch["slug"],
            content=html_body,
            chapters=chapters,
            prev_ch=prev_ch,
            next_ch=next_ch,
        )

        out = chapters_dir / f"{ch['slug']}.html"
        out.write_text(full_html, encoding="utf-8")
        print(f"OK: {ch['slug']}.html")

    # index.html 生成（カテゴリ分けして表示）
    categories = group_chapters_by_category(chapters)
    index_html = INDEX_TEMPLATE.render(categories=categories)
    (OUTPUT_DIR / "index.html").write_text(index_html, encoding="utf-8")
    print("OK: index.html")

    # repo直下 assets/ を docs/ へコピー（CSS/JS/OGP無しで公開される事故防止）
    shutil.copytree(Path(__file__).parent / "assets", OUTPUT_DIR / "assets", dirs_exist_ok=True)
    print("OK: assets copy → docs/assets/")

    print(f"\n完了: {len(chapters)}話 + index → {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
