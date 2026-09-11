<!-- published: 2026-09-11 / 種別: ものづくりの流れ / 対象スキル: reverse-engineer-song -->

# 013の次に見えた「聴くだけじゃ足りない」

ある日ふくけいは思った。YouTubeで流れてくる曲のMV、なんで自分はいつも「いい曲だな」で止まってしまうんだろう。曲の仕組みがまったく読めない。映像の動かし方も、どういうプロンプトで作れば再現できるのか、想像がつかない。

そこで、3つの生成AIで「同じものをもう一度作れるようにする」ためのスキルを作ることにした。音楽をSunoで、映像をRunwayで、静止画をMidjourneyで作れるよう、YouTubeのURL1つから4種類のプロンプト仕様書を組み立てる。

最初は「YouTubeを見て、聴くだけ」でやろうとしていた。でも、それだと音と映像の中間にある情報——BPM、テンポ推移、コード進行、メロディの形——が取れない。分析は全部、AI（Gemini）に任せるしかなかった。「見る」と「聴く」と「分析する」を分離し、3つの役割を1つのスキルに収めたのがこの設計の要点だった。

出来上がったスキルは、ふくけいが「いいな」と思った曲に対して、もう一度「作れそう」と思える入口になった。完全再現ではなく、「自分なりの別バージョン」を作るための種としてのプロンプト仕様書。聴く側から、手を動かす側に回るための道具だ。

---

<details><summary>▶ 技術的にどうなってるか</summary>

- **役割分離**: YouTube視聴（CCがYouTubeを直接見れない制約）はMCP `exa`/`WebSearch`経由でメタ取得・Gemini APIに楽曲分析を委任（scripts/api/gemini.py）・CCは結果の構造化と4種類プロンプト仕様書（音楽・画像・動画・テキスト）の整形を担当
- **依存ファイル**: `~/.claude/skills/reverse-engineer-song/SKILL.md`・`scripts/api/gemini.py`・Gemini APIキー（`~/.secrets.env`の`GEMINI_API_KEY`）
- **経緯**: 2026-06-15にマスタープロンプトSSOT作成・Suno型（歌詞+ジャンル+ムード+構成タグ）・Midjourney型（カメラ/照明/カラーパレット）・Runway型（モーションキーワード）3つのテンプレを統合

</details>

---

## 🔗 関連

- 元記録: 01_DECISIONS/ai-music/2026-06-15_reverse-engineer-songスキル_plan.md（要約参照・原文URLは非公開）
- 関連スキル: `reverse-engineer-song`・`analyze-song`・`make-song`（CC環境で楽曲を扱う3点セット）
