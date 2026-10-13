---
title: "迷子のdurable-cronが9c351486を発射していた話"
date: 2026-10-13
episode: 052
status: published
---

# 迷子のdurable-cronが9c351486を発射していた話

ある日、ログに9c351486という見慣れないIDが散見されるようになった。どこが発射源なのか調べると、`claude-config/scripts/auto-dev/` 配下に、その痕跡があった。

発射源は `durability` の頭文字dから始まるIDで、**durable cron** と呼ばれる種類だった。これは毎朝8時に走る定型ジョブ群で、ふくけいが「触らないでも回る」完成形を目指して設計された自動実行群だ。

ところが、9c351486 は普段見ないものだった。`apply-crons.sh reconcile` を走らせると、定義には無いcronが幽霊のように登録されていた。誰かが `CronCreate` で登録したまま消し忘れたか、あるいは別タブの並行実行が消し合いを起こしたか。

調査を進めると、**過去の発火記録は10-05 で止まっていた**。9c351486 は登録だけされて動いていない**ゾンビ cron** だった。apply-crons が「この定義は知らない」と叫び続けても、cron daemon 側では何も起きない。**沈黙するバグ**の典型例だ。

教訓は3つ。①durable cron は `CronCreate` 直後の `apply-crons reconcile` で登録が反映されるが、**その逆経路で削除が反映されるとは限らない**。②並行セッションが同じIDで別時刻に登録すると、定義上書きと適用タイミングの競合で片方が残る。③幽霊cronの検出は**reconcile の create/ghost 出力の差分**を毎週確認する以外にない。

この発見を契機に、apply-crons の ghost 検知強化と、cron の生存確認を `automation-health-report.sh` に組み込む運用ルールが新設された。「触らないでも回る」は「触らなくて良い」と「触ってはいけない」の境界が曖昧で、**境界を機械で監視する仕組み**が必要なのだという、当たり前の結論に至った。

---

<details>
<summary>▶ 技術的にどうなってるか</summary>

- `apply-crons.sh reconcile` は `durable_cron.yaml` を読んで全CronCreateのID・時刻・プロンプトを比較し、差分を `create`（追加必要）/ `ghost`（削除候補）/ `ok`（整合）の3状態で出力する
- 2026-10-13 の調査で 9c351486 は `ghost` リストに登場、しかし CronDelete 経路では消えない（apply-crons は reconcile のみ担当・実削除は `durable_cron.yaml` 側を編集する責任分担）
- 並行セッションが `CronCreate` を時間差で実行すると、後発が上書きされずに**両方の定義がマージ**される事例が過去にもあった
- 9c351486 の正体: 9月中旬の `zai-direct-refresh` 増設時に並行セッションが登録、片方だけ reconcile swap の競争で残ったもの（推定）
- 詳細: 01_DECISIONS/claude-code/2026-10-13_迷子durable-cron9c351486発見と除去.md
</details>
