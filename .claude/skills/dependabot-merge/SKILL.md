---
name: dependabot-merge
description: Reviews this BOM repository's open Dependabot pull requests for security and upstream-change risk, merges the ones that are clean, then bumps the patch version and pushes a release tag. Use this whenever the user mentions Dependabot, dependency update PRs, "依存更新", bumping library versions, or asks to review/merge/release the pending version-bump PRs — including phrasings that never say "Dependabot", such as "溜まってる更新PRを見て問題なければ入れて" or "ライブラリ上げてリリースして".
---

# Dependabot PR のレビューとリリース

このリポジトリは `build.gradle.kts` の `constraints` だけがバージョンの情報源です。
Dependabot の PR はほぼ全て、この 1 ファイルの 1〜数行を書き換えるだけのものです。
だからこそ「差分を見た」だけではレビューになりません。**変わったのは数字なので、
確認すべき実体は上流側にあります。**

このスキルは次の順で進みます。

1. 対象の PR を集める
2. 各 PR を 3 つの観点でレビューする
3. 問題がなければマージする（問題があれば残して報告する）
4. 全部片付いたらパッチバージョンを上げてタグを push する

## 前提の確認

先に壊れた状態で始めないための確認です。ここで止まる方が、途中で中断するより安全です。

```bash
gh auth status                     # 認証済みか
git status --porcelain             # 空であること（未コミットの変更があるなら先に相談する）
git rev-parse --abbrev-ref HEAD    # main であること
git fetch origin && git status -sb # origin/main と乖離していないこと
```

作業ツリーが汚れている、main 以外にいる、origin より進んでいる —— いずれかなら
勝手に片付けずユーザーに伝えて止まってください。マージとタグ push は取り消しが
面倒な操作なので、前提が崩れているときは進めない方が確実に得です。

## 1. 対象の PR を集める

```bash
gh pr list --author "app/dependabot" --state open \
  --json number,title,url,mergeable,mergeStateStatus,headRefName,createdAt
```

0 件なら「更新 PR はありません」と伝えて終わりです。バージョンを上げる必要も
ありません（上げるものが無いので）。

各 PR の中身は次で取れます。

```bash
gh pr view <番号> --json title,body,files
gh pr diff <番号>
```

`.github/dependabot.yml` で `groups` を設定しているため、**1 つの PR が複数の
アーティファクトを同時に上げることがあります**（ktor の 4 件など）。
`gh pr diff` を見て、実際に変わった座標と旧→新バージョンを漏れなく列挙してください。
`val ktor = "3.5.1"` のような共有バージョンの行が変わっている場合、その `val` を
使っている全ての `api(...)` が影響を受けます。

## 2. 各 PR をレビューする

3 つの観点で見ます。1 つでも赤信号が出たらマージしません。

### 2-1. 既知の脆弱性を照合する

新バージョンに既知の脆弱性が残っていないか、GitHub Advisory Database で確認します。

```bash
gh api -X GET /advisories \
  -f ecosystem=maven \
  -f affects="io.ktor:ktor-client-core" \
  --jq '.[] | {ghsa: .ghsa_id, severity, summary,
               ranges: [.vulnerabilities[] | select(.package.name == "io.ktor:ktor-client-core")
                        | {vulnerable: .vulnerable_version_range, patched: .first_patched_version}]}'
```

`vulnerable_version_range` に**新**バージョンが入っていたら、そのアップデートは
脆弱なバージョンへの更新です。止めて報告してください。
旧バージョンが範囲に入っていて新バージョンが外れているなら、それは脆弱性修正を
取り込む更新なので、報告時に「セキュリティ修正あり」と明示すると価値が伝わります。

`affects` は `group:artifact` 形式です。グループ PR では変わった座標それぞれで引いてください。

### 2-2. 上流のリリースノートを読む

Dependabot の PR 本文には、上流のリリースノートと commit 一覧が埋め込まれています。
まずそれを読み、足りなければ上流リポジトリを直接見ます。

```bash
gh release view <タグ> --repo <owner>/<repo> 2>/dev/null
```

上流リポジトリが分からないときは Maven Central の POM から引けます。

```bash
curl -sS https://repo1.maven.org/maven2/io/ktor/ktor-client-core/3.6.0/ktor-client-core-3.6.0.pom \
  | grep -oE 'https://github.com/[^<]+'
```

見るべきもの:

- セキュリティ修正の記載（あれば優先度が上がる）
- 破壊的変更 / 非推奨化（BOM 利用側のビルドを壊す）
- **新しい推移的依存の追加**（BOM の管理範囲外のライブラリが増える）
- ライセンス変更

### 2-3. 上流のコード差分を見る

リリースノートは書かれていることしか分かりません。**書かれていない変更を見つけるのが
ここの目的です。** タグ間の差分を取ります。

```bash
gh api repos/<owner>/<repo>/compare/<旧タグ>...<新タグ> \
  --jq '{commits: .total_commits, files: .files | length,
         authors: [.commits[].author.login] | unique}'
```

差分が大きいときは、全部読もうとせず次を優先して見てください。ここが供給網攻撃の
実際の入り口になる箇所だからです。

- ビルドスクリプト・CI 設定の変更（`build.gradle*`, `pom.xml`, `.github/workflows/`）
- 新規に追加されたネットワークアクセス、`exec` / `ProcessBuilder`、リフレクション
- 依存関係の追加・置き換え
- 見慣れないコミット作者、レビューなしで入った大きな変更
- 難読化されたコード、エンコードされた文字列リテラル

```bash
gh api repos/<owner>/<repo>/compare/<旧>...<新> --jq '.files[].filename' | grep -E 'gradle|pom.xml|workflows|settings'
```

**BOM のアップデート（`spring-boot-dependencies` など）は例外です。** 数百件の
バージョン管理が動くため上流の全差分を読むのは現実的ではありません。代わりに
管理バージョンの差分を取ってください。何が動いたかはそこに全部出ます。

```bash
for v in <旧> <新>; do
  curl -sS "https://repo1.maven.org/maven2/org/springframework/boot/spring-boot-dependencies/$v/spring-boot-dependencies-$v.pom" \
    > /tmp/sbdeps-$v.pom
done
# 2 つの POM の <properties> を比べ、動いたバージョンを一覧化する
```

このリポジトリは Spring Boot の管理下にあるものを重複して書かない方針なので、
Spring Boot 側が上げたバージョンと自前の `constraints` が衝突していないかも
ここで確認できます（Gradle は競合時に高い方を選びます）。

## 3. マージするか決める

**マージしてよい**のは、3 観点すべてで問題が無く、ビルドが通る場合だけです。
このリポジトリには CI が無いため、ビルド確認はローカルで行います。

```bash
git fetch origin <PR のブランチ名>
git checkout <PR のブランチ名>
./gradlew build publishToMavenLocal
git checkout main
```

**止めて報告する**のは次のいずれかに当たるときです。自動で判断せず、ユーザーに
渡してください。

- 新バージョンに未修正の脆弱性がある
- 上流差分に説明のつかない変更がある（2-3 の赤信号）
- 破壊的変更がある、メジャーバージョンが上がっている
- ビルドが通らない
- リリースノートも差分も確認できない（上流が非公開、タグが無いなど）

判断に迷ったら止める側に倒してください。マージは後からでもできますが、
入れてしまったものを追うのは高くつきます。

## 4. マージする

問題の無い PR から順にマージします。

```bash
gh pr merge <番号> --squash --delete-branch
```

**このリポジトリでは PR 同士が必ず競合します。** 全ての Dependabot PR が
`build.gradle.kts` という同じファイルを書き換えるためです。1 つマージすると
残りは古くなります。

だから 1 件ずつ処理してください。マージ後、残りの PR の状態を確認します。

```bash
gh pr view <番号> --json mergeable,mergeStateStatus --jq '{mergeable, mergeStateStatus}'
```

`CONFLICTING` になっていたら Dependabot に rebase を依頼します。

```bash
gh pr comment <番号> --body "@dependabot rebase"
```

Dependabot の rebase は数分かかります。ポーリングして待ち、**10 分待っても
`MERGEABLE` にならなければそこで止めて報告してください。** 自分で衝突を
解決して force push するのは避けます。Dependabot の PR を書き換えると
Dependabot 側の追跡が壊れ、次回以降おかしな PR が出ます。

`--admin` やブランチ保護の迂回は使わないでください。保護がかかっているなら
それは意図された設定です。

## 5. パッチバージョンを上げてタグを push する

1 件でもマージできたら実行します。1 件もマージしていないなら、上げるものが
無いのでこの手順は飛ばしてください。

```bash
git checkout main && git pull origin main
```

`gradle.properties` の `version` を読み、**パッチ部分だけ** +1 します。
このリポジトリは `-SNAPSHOT` を使いません。タグと `version` は常に同じ値です。

```
1.0.0  ->  1.0.1   （タグは v1.0.1）
1.4.2  ->  1.4.3   （タグは v1.4.3）
```

`version` に `-SNAPSHOT` が付いている状態を見つけたら、それは意図しない変更です。
勝手に直さず報告してください。

上げたら発行まで確認します。BOM は POM が全てなので、生成物を見るのが唯一の検証です。

```bash
./gradlew build publishToMavenLocal
```

コミットしてタグを打ち、push します。JitPack はタグを見てビルドするため、
タグを push して初めて利用側から使えるようになります。

```bash
git add gradle.properties
git commit -m "Bump version to <新バージョン>"
git tag v<新バージョン>
git push origin main
git push origin v<新バージョン>
```

同名のタグが既にあるなら、上書きせず止めて報告してください。公開済みのタグを
動かすと、既にそのバージョンを取得した利用側と中身が食い違います。

## 6. 報告する

最後に何をしたかをまとめます。ユーザーが後から追える形にしてください。

```markdown
## マージした PR

| PR | 更新内容 | 確認したこと |
| --- | --- | --- |
| #12 | ktor 3.5.1 → 3.6.0（4 件） | 脆弱性なし / 破壊的変更なし / 上流差分 42 commits・不審な変更なし |

## 保留した PR

| PR | 更新内容 | 保留した理由 |
| --- | --- | --- |
| #15 | detekt 1.23.8 → 2.0.0 | メジャーアップ。ルール既定値が変わり利用側の検出結果が変わる |

## リリース

- `1.0.0` → `1.0.1`
- タグ `v1.0.1` を push（JitPack が拾います）
```

セキュリティ修正を取り込んだ更新があれば、それは目立つように書いてください。
利用側が「上げるべきか」を判断する材料になります。
