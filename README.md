# cc-stories-guide

CC（Claude Code）との作業を「専門用語なしの物語+技術解説」のペアで残す自分専用ガイド（GitHub Pages公開・読者は本人のみだがサイト自体は公開）。

- 公開URL: https://fukukei23.github.io/cc-stories-guide/
- 話の追加: `story` スキル（4段承認ゲート・spec v2 §4）を使う。手動追加は `source/NNN_<タイトル>.md` を作り `python3 convert.py` → denylist再走査 → commit+push

## 運用ルール
- **上限: 1日10話**（暴走止め・ふくけい指示2026-09-01）
- 公開前は必ず `python3 check_story_public.py <file> --denylist security-denylist.yaml` が EXIT=0
- denylistにヒットしたらマスク/削除して再実行（判定は「マッチ断片自身がwhitelist語を含む場合のみ許可」）

## gitleaks 方針（確定）
- **現時点は未導入**。第2ゲート（denylist+人間の全文確認）で代替中。
- **導入判断**: 話が10話を超えるか、機密度の高い話（実キーが登場し得る話題）を書く前に `gitleaks detect --source .` を第2ゲートに追加する

## 基盤同期手順（convert.py等の共通基盤を更新した時）
1. 元リポジトリ（例: `~/projects/ai-trending-guide/convert.py`）で変更を確定させる
2. 本リポジトリへ `cp` → stories向け調整箇所（docstring・サイト名・INDEX_CATEGORIES・mermaid/サニタイズ非搭載）を再適用
3. `python3 convert.py && git add convert.py docs && git commit && git push`
4. 他のガイドリポジトリにも同様の変更が必要か確認（16リポ運用・N+1保守は受け入れた方針）

## 先送り（Phase 2）
- new-session締め時の自動提案（判定Phase組込）
- 記事の鮮度注記ルール・denylist 30日未更新警告
