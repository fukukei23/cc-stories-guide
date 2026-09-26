"""fence（コードブロック）領域判定とメタコメント除去の共通実装.

convert.py / generate_story_candidates.py で二重実装だったfence状態遷移を
1か所に集約する（verify r3 issue 3・DRY対応・2026-09-27）.
"""

from __future__ import annotations

import re

# CommonMark準拠: fence開始は 0-3スペースのインデントのみ・タブ不許可
# （4スペール以上はインデントコードブロックでfence不成立・verify r3 issue 2）
_FENCE_LINE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")

# コメントスパンを先に判定する交互オーダー（コメント内のバックティックペアで
# コメント検出が壊れないようにする・verify r3 issue 1）
_COMMENT_OR_INLINE = re.compile(r"(<!--.*?-->)|(`[^`\n]*`)", re.DOTALL)


def is_fence_line(line: str) -> bool:
    """行がfenceマーカー行（0-3スペース+3個以上のバックティック/チルダ）か."""
    return _FENCE_LINE.match(line) is not None


def split_fenced_parts(text: str) -> list[tuple[bool, str]]:
    """テキストを (is_fence, part) のリストに分割する.

    行単位の状態遷移で判定する（verify r2 issue 1対応）: re.split系の
    「偶数個のfence前提」は奇数個（閉じ忘れ）で以降が無音にfence扱い/非fence扱いと
    なり、コメント除去が無音無効化される欠陥があった。本実装はCommonMark準拠の
    挙動（開くfence=情報文字列可・閉じるfence=同種かつ同長以上かつ後続なし）で
    閉じ忘れfence以降はコードとして保持し、判定は決定論的.
    """
    parts: list[tuple[bool, str]] = []
    pending: list[str] = []
    fence: list[str] | None = None
    fence_char = ""
    fence_len = 0
    for ln in text.splitlines(keepends=True):
        m = _FENCE_LINE.match(ln)
        if fence is None:
            if m:
                parts.append((False, "".join(pending)))
                pending = []
                fence = [ln]
                fence_char, fence_len = m.group(1)[0], len(m.group(1))
            else:
                pending.append(ln)
        else:
            fence.append(ln)
            if m and m.group(1)[0] == fence_char \
                    and len(m.group(1)) >= fence_len and m.group(2).strip() == "":
                parts.append((True, "".join(fence)))
                fence = None
    if pending:
        parts.append((False, "".join(pending)))
    if fence is not None:
        parts.append((True, "".join(fence)))  # 閉じ忘れfenceは末尾までコードとして保持
    return parts


def iter_comment_spans(text: str):
    """非fence領域のコメント（`<!-- ... -->`・複数行含む）の内容を列挙する.

    コードブロック（fence）内のコメント例は採集対象外（convert側の保持方針と
    整合させる・verify r2 issue 2の逆方向不整合防止）.
    """
    for is_fence, part in split_fenced_parts(text):
        if is_fence:
            continue
        for m in re.finditer(r"<!--(.*?)-->", part, re.DOTALL):
            yield m.group(1)


def drop_meta_comments(block: str) -> str:
    """非fenceブロックから `published:` / `素材:` を含むHTMLコメントを除去する.

    コメントスパンを最優先で判定し、コメント**内**のバックティックペアに影響され
    ない（コメントスパン先・インラインコード保護後の交互オーダー・verify r3
    issue 1対応）。インラインコード（バックティック1個・同一行内ペア）内の
    コメント表記は本文の説明言及として保持する（verify r2 issue 3）.
    """
    out: list[str] = []
    last = 0
    for m in _COMMENT_OR_INLINE.finditer(block):
        comment = m.group(1)
        if comment and ("published:" in comment or "素材:" in comment):
            out.append(block[last:m.start()])
            last = m.end()
    out.append(block[last:])
    return "".join(out)
