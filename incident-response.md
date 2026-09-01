# インシデント対応（誤公開時の手順）

> 作業物語ガイド（GitHub Pages公開・読者は本人のみだがサイト自体は公開）で
> 機密情報を含む話を誤って公開してしまった場合の手順。**発見から30分以内の対応を目標**にする。

## 1. 即時非公開化（数秒で効く）
```bash
gh api -X PATCH repos/fukukei23/cc-stories-guide/pages -f enabled=false
```
- ※ トークンにPages権限が無く403になる場合は **Settings → Pages → ⋯（ゴミ箱/Delete site）** でWeb UIから削除
- サイト自体が消えるため閲覧は即座に止まる

## 2. 当該話の削除
```bash
git rm source/NNN_<slug>.md && python3 convert.py && git add docs && git commit -m "remove: 誤公開話の削除" && git push
```

## 3. 履歴消去（機密がgit履歴に残る場合のみ）
```bash
# ⚠️ git push --force はデフォルト禁止のため、実行前に必ずふくけい承認を取る
pip install git-filter-repo
git filter-repo --invert-paths --path source/NNN_<slug>.md
git push origin --force --all   # 承認済みの場合のみ
```
- 履歴消去後はクローン全員の再クローンが必要（本リポは個人利用のため実害小）

## 4. キャッシュ・インデックス対策
- Google検索からの削除申請: https://www.google.com/webmasters/tools/removals
- Internet Archive: https://web.archive.org/ で自サイトURLを検索し、あればremove申請

## 5. 事後対応
- `security-denylist.yaml` に同型を検知するパターンを追加（再発防止）
- `check_story_public.py` が捕まえられなかった経路を01_DECISIONSに記録（claude-code project）
- ふくけいへの報告: 何が・いつまで・誰かに見られ得たか

## 予防（日常運用）
- publish前は必ず `python3 check_story_public.py <file>` が EXIT=0 であること（4段ゲート・spec v2 §4）
- gitleaks未導入: 導入候補（`gitleaks detect --source .` をpush前手順に足すと二重防御になる）
