---
name: dependabot-merge
description: Reviews this BOM repository's open Dependabot pull requests for security and upstream-change risk, merges the ones that are clean, then bumps the patch version and pushes a release tag whose commit message carries the full review record. Use this whenever the user mentions Dependabot, dependency update PRs, "依存更新", bumping library versions, or asks to review/merge/release the pending version-bump PRs — including phrasings that never say "Dependabot", such as "溜まってる更新PRを見て問題なければ入れて" or "ライブラリ上げてリリースして".
---

# Dependabot PR のレビューとリリース

このリポジトリは `build.gradle.kts` の `constraints` だけがバージョンの情報源です。
Dependabot の PR はほぼ全て、この 1 ファイルの 1〜数行を書き換えるだけです。
つまり **差分を見ても数字しか分かりません。確認すべき実体は上流側にあります。**

役割分担がこのスキルの要点です。

- **あなた（このスキルを実行する側）** — 手順の進行、マージ、リリース。判断は
  サブエージェントの評決に従います。自分で脆弱性を調べようとしないでください。
- **Opus のサブエージェント** — PR ごとの脆弱性・上流差分レビュー。ここは
  「リリースノートに書かれていない変更を見抜く」作業で、能力差がそのまま
  見落としになるため、意図的に上位モデルへ回しています。

## 0. 前提を確認する

```bash
gh auth status
git status --porcelain            # 空であること
git rev-parse --abbrev-ref HEAD   # main であること
git fetch origin && git status -sb # origin/main と乖離していないこと
```

作業ツリーが汚れている、main 以外にいる、origin より進んでいる —— どれか一つでも
当てはまるなら、片付けようとせずユーザーに伝えて止まってください。マージとタグ
push は取り消しが面倒なので、前提が崩れたまま進める価値はありません。

## 1. 対象の PR を集める

```bash
gh pr list --author "app/dependabot" --state open \
  --json number,title,url,mergeable,headRefName
```

0 件なら「更新 PR はありません」と伝えて終了です。バージョンも上げません。

PR ごとに、実際に動く座標と旧→新バージョンを確定させます。

```bash
gh pr view <番号> --json title,body
gh pr diff <番号>
```

`.github/dependabot.yml` で `groups` を設定しているので、**1 つの PR が複数の
アーティファクトを同時に上げます**（ktor なら 4 件）。`val ktor = "3.5.1"` のような
共有バージョンの行が変わっていたら、その `val` を参照している `api(...)` を
すべて洗い出してください。この一覧をサブエージェントに渡します。

## 2. 脆弱性レビューを Opus に投げる

**PR ごとに 1 エージェント。独立した作業なので、全 PR 分を同じメッセージ内で
まとめて起動してください**（逐次に投げると待ち時間が PR 数だけ積み上がります）。

Agent ツールで `model: "opus"`、`subagent_type: "general-purpose"` を指定し、
次のテンプレートの `<...>` を埋めて渡します。

```
あなたは Dependabot PR のセキュリティレビュー担当です。調査だけを行い、
リポジトリの状態を変更しないでください（merge / commit / push / ブランチ操作は禁止）。

対象 PR: #<番号> <タイトル>
更新される座標:
<group:artifact 旧バージョン -> 新バージョン を1行ずつ>

次の 3 点を必ず確認してください。

1. 既知の脆弱性
   gh api -X GET /advisories -f ecosystem=maven -f affects="<group:artifact>" \
     --jq '.[] | {ghsa: .ghsa_id, severity, summary,
                  ranges: [.vulnerabilities[] | select(.package.name == "<group:artifact>")
                           | {vulnerable: .vulnerable_version_range, patched: .first_patched_version}]}'
   を座標ごとに実行する。新バージョンが vulnerable_version_range に入っていれば
   「脆弱なバージョンへの更新」なので HOLD。旧バージョンだけが範囲内で新バージョンが
   外れているなら、それはセキュリティ修正の取り込みなので明記する。

2. 上流のリリースノート
   PR 本文に埋め込まれたリリースノートを読む。足りなければ
   gh release view <タグ> --repo <owner>/<repo> を見る。上流リポジトリが不明なら
   curl -sS https://repo1.maven.org/maven2/<group をスラッシュ区切りに>/<artifact>/<新バージョン>/<artifact>-<新バージョン>.pom \
     | grep -oE 'https://github.com/[^<]+'
   で引ける。破壊的変更・非推奨化・新しい推移的依存の追加・ライセンス変更を見る。

3. 上流のコード差分
   gh api repos/<owner>/<repo>/compare/<旧タグ>...<新タグ> --jq '.files[].filename'
   リリースノートに書かれていない変更を見つけるのが目的。差分が大きいときは
   ビルドスクリプト・CI 設定 (build.gradle*, pom.xml, .github/workflows/)、
   新規のネットワークアクセスや exec/ProcessBuilder、依存の追加・置換、
   見慣れないコミット作者、難読化されたコードやエンコード文字列を優先して見る。
   タグが存在せず差分が取れない場合は、その事実を必ず報告に含めること
   （「確認した」と書かないこと）。

BOM の更新（spring-boot-dependencies など）は上流の全差分を読むのが非現実的なので、
代わりに管理バージョンの差分を取ること。新旧の POM を取得して <properties> を比べる。

最後に、必ずこの形式で終えてください。

VERDICT: MERGE または HOLD
REASON: 1 行の理由
DETAIL:
（確認内容。表にできるならする。確認できなかったことも書く）

迷ったら HOLD。マージは後からできるが、入れたものを追うのは高くつく。
未修正の脆弱性 / 説明のつかない上流変更 / 破壊的変更 / メジャーアップ /
リリースノートも差分も確認できない、のいずれかなら HOLD。
```

評決が出るまで待ちます。**あなたが評決を上書きしないでください。**
HOLD の PR はマージせず、理由をそのまま報告に載せます。

## 3. マージする

CI が無いので、ビルド確認はローカルで行います。VERDICT が MERGE の PR について、

```bash
git fetch origin <PR のブランチ名>
git checkout <PR のブランチ名>
./gradlew build publishToMavenLocal
git checkout main
```

が通ったらマージします。通らなければ HOLD 扱いにして報告してください。

```bash
gh pr merge <番号> --squash --delete-branch
```

**1 件ずつ処理してください。** 共有バージョンの `val` がファイル冒頭に固まって
並んでいるため、squash マージの後、隣接する行を触る PR は 3-way マージが解決できず
競合します（`val ktor` と `val kotest` のように隣同士が該当）。`constraints` の中の
離れた行を触る PR は競合しません。

マージ後、残りの PR の状態を確認します。

```bash
gh pr view <番号> --json mergeable --jq .mergeable
```

`CONFLICTING` なら Dependabot に作り直させます。

```bash
gh pr comment <番号> --body "@dependabot rebase"
```

rebase には数分かかります。ポーリングして待ち、**10 分待っても `MERGEABLE` に
ならなければ止めて報告してください。** 自分で競合を解決して force push しては
いけません。Dependabot の PR を書き換えると Dependabot 側の追跡が壊れ、次回以降
おかしな PR が出ます。`--admin` やブランチ保護の迂回も使わないでください。

## 4. バージョンを上げる

1 件でもマージできた場合だけ実行します。0 件なら上げるものが無いので飛ばします。

```bash
git checkout main && git pull origin main
python3 .claude/skills/dependabot-merge/scripts/next-version.py --apply
```

パッチ +1、タグ名、`-SNAPSHOT` の混入チェック、タグの重複チェックはこの
スクリプトが行います。**手で計算しないでください。** スクリプトが非ゼロで
終了したら、その内容をユーザーに伝えて止まってください。

発行まで確認します。BOM は POM が全てなので、生成物を見るのが唯一の検証です。

```bash
./gradlew build publishToMavenLocal
```

## 5. 報告をコミットログに残して push する

**このスキルの成果物はコミットログです。** BOM のバージョンだけを見ても、何が
どういう根拠で入ったのかは分かりません。`git log` にレビュー内容が残っていれば、
後から「なぜこのバージョンなのか」を追えます。ユーザーへのチャット出力は消えます。

報告を組み立ててファイルに書き、それをコミットメッセージにします。

```bash
cat > /tmp/release-notes.txt <<'EOF'
Bump version to <新バージョン>

## マージした PR

| PR | 更新内容 | 確認したこと |
| --- | --- | --- |
| #12 | ktor 3.5.1 -> 3.6.0 (4 件) | 脆弱性なし / 破壊的変更なし / 上流差分 42 commits・不審な変更なし |

## 保留した PR

| PR | 更新内容 | 保留した理由 |
| --- | --- | --- |
| #15 | detekt 1.23.8 -> 2.0.0 | メジャーアップ。ルール既定値が変わり利用側の検出結果が変わる |

## 確認できなかったこと

- mockk 1.14.12 は上流にタグが無く、タグ間差分は未確認
EOF

git add gradle.properties
git commit -F /tmp/release-notes.txt
git tag v<新バージョン>
git push origin main
git push origin v<新バージョン>
```

各サブエージェントが返した DETAIL をそのまま貼るのではなく、表の 1 行に畳んでください。
ただし **HOLD の理由と、確認できなかったことは省略しないでください。** そこが後から
効いてくる情報です。セキュリティ修正を取り込んだ更新があれば目立つ位置に書きます。

タグを push して初めて JitPack がビルドし、利用側から使えるようになります。

## 6. ユーザーに伝える

コミットログに全部入っているので、チャットには要約だけで十分です。

- マージした PR の番号と更新内容
- 保留した PR と、その理由
- 新しいバージョンとタグ
- 判断を仰ぎたいことがあればそれ
