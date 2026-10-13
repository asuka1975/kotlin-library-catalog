# kotlin-library-catalog

複数プロジェクトで使うライブラリの**バージョンを統一する**ための BOM です。
`java-platform` プラグインで constraints を定義し、Maven 形式で発行すると
POM の `dependencyManagement` として利用できます。

利用側は依存にバージョンを書かず、この BOM のバージョンだけを指定します。

```
kotlin-library-catalog/
├── build.gradle.kts     ← ここにバージョンを書く
├── settings.gradle.kts
├── gradle.properties    ← group / version
├── jitpack.yml
└── gradlew, gradle/wrapper/
```

## ライブラリを追加・更新する

`build.gradle.kts` の `constraints` ブロックを編集します。

```kotlin
constraints {
    api("io.arrow-kt:arrow-core:2.0.1")
}
```

`constraints` は「そのライブラリが使われたときのバージョン」を決めるだけで、
依存として追加はされません。利用側が使っていないものが混ざっていても影響ありません。

複数のライブラリでバージョンを共有する場合は、ファイル冒頭の `val` を使います。

```kotlin
val ktor = "3.5.1"
```

## Dependabot

`.github/dependabot.yml` を置いてあります。GitHub に push すると、毎週月曜に
`build.gradle.kts` の `constraints` を走査して更新 PR を作ります。

`val ktor = "3.5.1"` のようにバージョンを共有しているものは 1 つ更新すると
同じ `val` を使う全てが動くため、PR が衝突しないよう `groups` でまとめてあります。
共有バージョンのライブラリを追加したときは `groups` にも `patterns` を足してください。

Gradle Wrapper も `gradle` エコシステムの対象で、Dependabot が更新 PR を出します。

手動で更新する場合は次のようにします。`wrapper` タスクを 2 回実行するのは、
1 回目では `gradle-wrapper.properties` しか更新されず、`gradlew` と
`gradle-wrapper.jar` が古いまま残るためです。

```bash
SUM=$(curl -sSL https://services.gradle.org/distributions/gradle-<version>-bin.zip.sha256)
./gradlew wrapper --gradle-version <version> --gradle-distribution-sha256-sum "$SUM"
./gradlew wrapper --gradle-version <version> --gradle-distribution-sha256-sum "$SUM"
```

`distributionSha256Sum` を入れておくと、配布物が差し替わったときにビルドが失敗します。
値を間違えると新規クローンと JitPack のビルドが全部壊れるので、更新後は
`~/.gradle/wrapper/dists/gradle-<version>-bin` を消して再ダウンロードさせ、
検証が通ることを確認してください。

## 更新 PR の自動レビューとリリース

`.github/workflows/dependabot-review-release.yml` が **毎週火曜 00:00 (JST)** に動きます。
Dependabot が月曜 09:00 に PR を作る 15 時間後です（GitHub の cron は UTC 固定なので、
ファイル上は `0 15 * * 1` と書いてあります）。

開いている Dependabot PR ごとに、Claude Opus 5.5（`claude-opus-5-5`）を Claude Code の
CLI で走らせ、既知の脆弱性・上流のリリースノート・上流のタグ間差分を確認させます。
評決が `MERGE` ならブランチをビルドしてからマージ、`HOLD` なら理由をコメントしてクローズします。1 件でも
マージできたらパッチバージョンを上げ、レビュー内容をコミットメッセージに入れてタグを
push します（タグを push して初めて JitPack がビルドします）。

**このワークフローが見ているのはセキュリティだけです。** 脆弱性・悪意あるコード・供給網の
汚染が無ければマージします。破壊的変更・メジャーアップ・非推奨化は `HOLD` の理由に
しません。互換性の問題は利用側のビルドで顕在化しますが、脆弱性は黙って通るからです。
気づいた非互換はリリースコミットの「確認したこと」欄に `注意:` として併記されるので、
BOM を上げる側はそこを見てください。

使うモデルはワークフローの `env.CLAUDE_MODEL` 一箇所で決まります。PR のクローズ理由の
コメントにも、リリースコミットの記録にもそこから流れるので、切り替えるときはこの 1 行
だけ書き換えてください。確認すべき観点は `.github/scripts/review-prompt.md` 側に
書き下してあるので、モデルを変えても手順は変わりません。

[Claude Code Action](https://github.com/anthropics/claude-code-action) は使わず、
ワークフローの中で Claude Code の CLI を直接動かしています。アクション経由の呼び出し
だけが、残高があっても `Credit balance is too low` で拒否される不具合があるためです
（anthropics/claude-code-action#1888）。CLI のバージョンはワークフローの
`env.CLAUDE_CODE_VERSION` で固定していて、Dependabot は追わないので、上げるときは手で
書き換えてください。アクションに戻すときの注意は、ワークフロー冒頭のコメントに
あります。

レビューするモデルには**書き込み権限を渡していません**。モデルが読むのは PR 本文に
埋め込まれた上流のリリースノート、つまり第三者が書ける文章です。それを読んだ
エージェント自身がマージまでできると、このワークフローが防ごうとしている攻撃が
そのまま通ります。ジョブを分け、レビュー側のトークンを読み取り専用にしてあります。
実行できるコマンドも `gh` の参照系・Maven Central からの `curl`・Gradle 公式の
チェックサムの取得・出力の絞り込みとハッシュ計算だけに限っていて（ワークフローの `--allowedTools`）、それ以外は確認なしで拒否されます。
許すコマンドを変えるときは、`review-prompt.md` の「使えるコマンド」も合わせて直してください。

動かすのに必要な設定は次の 3 つです。

- Claude Console で ID フェデレーション（Workload Identity Federation）を設定する
  （次の節）
- リポジトリの Secrets（Settings > Secrets and variables > Actions > Secrets）に、
  Console で作った ID を登録する。識別子で秘密ではないが、公開リポジトリのログに
  組織 ID が出ないよう Secrets に置いている
  - `ANTHROPIC_FEDERATION_RULE_ID`: フェデレーションルールの ID（`fdrl_...`）
  - `ANTHROPIC_ORGANIZATION_ID`: 組織 ID（Console の Settings > Organization）
  - `ANTHROPIC_SERVICE_ACCOUNT_ID`: ルールの対象のサービスアカウント ID（`svac_...`）
  - `ANTHROPIC_WORKSPACE_ID`: ワークスペース ID（`wrkspc_...`）。ルールが 1 つの
    ワークスペースだけを対象にしているなら不要
- Settings > Actions > General > Workflow permissions が
  「Read repository contents and packages permissions」に絞られていないこと
  （ワークフロー側で `permissions:` を宣言しているので、この既定値のままで動きます。
  組織ポリシーで write を禁止している場合はタグ push が落ちます）

`main` にブランチ保護をかけている場合、リリースコミットの push が拒否されます。
bot を除外するか、保護を外してください。

手を入れたら Actions タブから手動実行できます。`dry_run` は既定で `true` で、
レビューとビルド確認だけを行い、マージ・クローズ・タグ push はしません。

評決が取れなかった PR（API 障害、出力が壊れた、ジョブが落ちた）は**触りません**。
「調べていない」は「問題なし」ではないので、open のまま残して次回に回します。
評決は ERROR になり、API で落ちた回は理由に API エラーの種類と HTTP ステータスが
残ります（`authentication_failed / HTTP 401 / ...`、`billing_error / HTTP 400 / ...` など）。
ジョブの Summary か成果物の `verdict-<PR 番号>` で見られます。

### Claude API の認証（ID フェデレーション）

API キーを Secrets に置かず、ジョブが GitHub から受け取る OIDC トークンを、Claude API の
短命なアクセストークンに交換して使います。漏れて困る長期の秘密がリポジトリに無く、
ローテーションも要りません。課金は Claude Console の組織に対する API の従量課金です
（Claude の Pro / Max プランの利用枠では動きません）。

Claude Console の Settings > Workload identity で Connect workload を選び、GitHub Actions
のタイルから作ります。発行者は `https://token.actions.githubusercontent.com` で、
ウィザードが埋めてくれます。フェデレーションルールの一致条件は次のとおりにします。

| 項目 | 値 |
| --- | --- |
| subject（`subject_prefix`） | `repo:asuka1975@39215088/kotlin-library-catalog@1314453069:*` |
| audience | `https://api.anthropic.com` |
| claims | `ref` = `refs/heads/main` |
| claims | `job_workflow_ref` = `asuka1975/kotlin-library-catalog/.github/workflows/dependabot-review-release.yml@refs/heads/main` |

スコープはウィザード既定の `workspace:developer`、トークンの有効期間は既定の 600 秒の
ままで構いません。ワークフローが GitHub の OIDC トークンを 1 分おきに取り直すので、
レビューが長引いてもアクセストークンは期限ごとに交換し直されます。

claims には、この 2 つ以外を足さないでください。とくに `event_name` は入れては
いけません。このワークフローは手動実行では `workflow_dispatch`、定期実行では
`schedule` になるので、どちらの値にしても片方で落ちます。手動実行の dry run が通っても、
定期実行で通る保証にはなりません。値は文字列として完全に一致する必要があり、
大文字小文字や前後の空白が違っても一致しません。

subject がよく見る `repo:<owner>/<repo>:...` の形でないのは、このリポジトリの OIDC
トークンがオーナーとリポジトリの不変 ID を含む subject を使う設定（`use_immutable_subject`）
になっているためです。今の形式は次で確かめられます。

```bash
gh api repos/asuka1975/kotlin-library-catalog/actions/oidc/customization/sub
```

ここがずれると交換は 401 で拒否され、Console の認証履歴に `match_subject_prefix` と
残ります。

subject は前方一致でリポジトリを不変 ID で押さえるだけにし、ブランチとワークフローは
claims で絞っています。subject の末尾はイベントの種類で変わる（`ref:...` /
`pull_request` など）ので、そこに依存しない形にしてあります。

ルールは main 上のこのワークフローだけに絞ってあります。定期実行は main で動くので
これで足り、fork からの PR やほかのブランチ・ワークフローではトークンを取れません。
手動実行もブランチに main を選んだときだけ通ります。ブランチでワークフローを試すと
認証で落ち、全 PR が ERROR（触らない）になります。ワークフローのファイル名を変えたら
`job_workflow_ref` も直してください。

交換が拒否されると、レビューは ERROR（PR には触らない）になり、理由に
`authentication_failed / HTTP 401 / ...` と出ます。401 の応答には、どの条件が合わなかった
かは書かれません。推測で直す前に、Console の Settings > Workload identity にある
認証履歴を見てください。照合したトークンのクレームの実際の値と、拒否理由が残って
います。`match_subject_prefix` なら subject、`match_claim_value_mismatch` なら claims が、
トークンの中身と合っていません。

Console で Connect workload をやり直すと、ルール（`fdrl_...`）とサービスアカウント
（`svac_...`）が新しく作られます。やり直したら Secrets の 4 つを見直してください。
新しく作ったサービスアカウントが自動で入るのは Default ワークスペースだけなので、
`ANTHROPIC_WORKSPACE_ID` のワークスペースを使うなら、そのメンバーに足してください。

以前使っていた Secrets の `SAKANA_API_KEY` はもう使わないので、削除して構いません。
`ANTHROPIC_API_KEY` などの静的な認証情報をワークフローに足すとそちらが優先され、
フェデレーションが使われなくなるので、足さないでください。

## ローカルで確認する

```bash
./gradlew publishToMavenLocal
```

生成された `dependencyManagement` は次で確認できます。

```bash
cat ~/.m2/repository/com/github/asuka1975/kotlin-library-catalog/1.0.0/kotlin-library-catalog-1.0.0.pom
```

## GitHub / JitPack で公開する

Gradle Wrapper を含めてコミットし、タグを打ちます。

```bash
git add -A && git commit -m "Initial BOM"
git remote add origin git@github.com:asuka1975/kotlin-library-catalog.git
git push -u origin main
git tag 1.0.0 && git push origin 1.0.0
```

https://jitpack.io でリポジトリを Look up すると、JitPack が
`./gradlew build publishToMavenLocal` を実行して公開します。

タグ名は `gradle.properties` の `version` と同じ値にします（`v` は付けません）。
こうしておくと、ローカル発行でも JitPack でも座標が一致します。

```
com.github.asuka1975:kotlin-library-catalog:1.0.0
```

`group` / `version` は `gradle.properties` の値が使われ、JitPack 上では JitPack が
注入する `GROUP` / `VERSION` 環境変数で上書きされます。JitPack の `VERSION` は
タグ名そのものなので、タグに `v` を付けると発行されるバージョンだけ `v1.0.0` に
なってしまい、`gradle.properties` と食い違います。

## 利用側の設定

### settings.gradle.kts

```kotlin
dependencyResolutionManagement {
    repositories {
        mavenCentral()
        maven { url = uri("https://jitpack.io") }   // JitPack は最後に置く
    }
}
```

### build.gradle.kts

```kotlin
dependencies {
    implementation(platform("com.github.asuka1975:kotlin-library-catalog:1.0.0"))

    // バージョンを書かない
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core")
    implementation("io.ktor:ktor-client-cio")
    implementation("io.github.oshai:kotlin-logging")

    testImplementation("io.kotest:kotest-runner-junit5")
}
```

BOM 自体のバージョン（`1.0.0`）は省略できません。

### バージョンを強制したい場合

`platform(...)` は「競合したらより高い方を選ぶ」ため、推移的依存によって BOM より
新しいバージョンが選ばれることがあります。BOM の値を強制するなら `enforcedPlatform(...)`
を使います。

```kotlin
implementation(enforcedPlatform("com.github.asuka1975:kotlin-library-catalog:1.0.0"))
```

ただしライブラリプロジェクトで `enforcedPlatform` を使うと、その利用者のバージョン選択まで
強制してしまいます。通常は `platform(...)` を基本にしてください。

## Spring Boot BOM の取り込みについて

`javaPlatform { allowDependencies() }` を有効にして
`spring-boot-dependencies` を import しているため、Spring / Jackson / Logback /
JUnit など **Spring Boot が管理する 648 件がそのまま利用できます**。

```kotlin
implementation("org.springframework.boot:spring-boot-starter-web")   // -> 4.1.0
implementation("com.fasterxml.jackson.module:jackson-module-kotlin") // -> 2.21.4
```

Spring を使わないプロジェクトでも、Jackson などを使ったときに同じバージョンに揃います。

Kotlin 関連も Spring Boot が BOM を import しているため、そちらの管理下になります。

| Spring Boot が import している BOM | バージョン | 対象 |
| --- | --- | --- |
| `org.jetbrains.kotlin:kotlin-bom` | 2.3.21 | `kotlin-stdlib` / `kotlin-reflect` など |
| `org.jetbrains.kotlinx:kotlinx-coroutines-bom` | 1.10.2 | `-core` / `-test` / `-reactor` など 17 件 |
| `org.jetbrains.kotlinx:kotlinx-serialization-bom` | 1.11.0 | `-json` / `-core` / `-protobuf` など 15 件 |

`kotlinx-datetime` だけは Spring Boot の管理対象外なので、この BOM で指定しています。

### 衝突したときの挙動

取り込んだ BOM と自前の `constraints` が同じライブラリを管理していると、
**Gradle は高い方を選びます**（Maven の `dependencyManagement` は先勝ちなので挙動が違います）。
自前の値が Spring Boot の検証済みの組み合わせを黙って上書きしてしまうため、
Spring Boot が管理しているものは重複して書かない方針にしています。

意図的に上書きしたい場合だけ `constraints` に書き足してください。その際は
Spring Boot 側のバージョンより高いことを確認してください（低いと Gradle 側では効きません）。

## detekt / ktlint について

**Gradle プラグインのバージョンはこの BOM では統一できません。**
プラグインは buildscript / plugin classpath で解決され、そこはプロジェクトの
依存関係とは別のため、`platform(...)` の影響を受けないからです。

この BOM が効くのは、プロジェクトの依存として宣言するアーティファクトです。

```kotlin
dependencies {
    implementation(platform("com.github.asuka1975:kotlin-library-catalog:1.0.0"))

    detektPlugins("io.gitlab.arturbosch.detekt:detekt-formatting")  // -> 1.23.8
}
```

プラグイン側のバージョンを揃えたい場合は、利用側の `settings.gradle.kts` で指定します。

```kotlin
pluginManagement {
    plugins {
        id("io.gitlab.arturbosch.detekt") version "1.23.8"
        id("org.jlleitschuh.gradle.ktlint") version "14.2.0"
    }
}
```

こうしておくと、各 `build.gradle.kts` では `id("io.gitlab.arturbosch.detekt")` と
バージョンなしで書けます。

## 他の BOM を取り込む

`build.gradle.kts` の `dependencies` に追加します（`allowDependencies()` は設定済み）。

```kotlin
api(platform("org.jetbrains.kotlin:kotlin-bom:2.4.10"))
```

## 管理しているライブラリ

| ライブラリ | バージョン |
| --- | --- |
| `org.springframework.boot:spring-boot-dependencies`（BOM import） | 4.1.0 |
| `org.jetbrains.kotlinx:kotlinx-datetime` | 0.8.0 |
| `io.ktor:ktor-client-core` / `-cio` / `-content-negotiation` / `ktor-serialization-kotlinx-json` | 3.5.1 |
| `io.kotest:kotest-runner-junit5` / `-assertions-core` / `-property` | 6.2.3 |
| `io.mockk:mockk` | 1.14.11 |
| `io.gitlab.arturbosch.detekt:detekt-formatting` / `-api` / `-cli` | 1.23.8 |
| `com.pinterest.ktlint:ktlint-cli` / `-rule-engine` / `-ruleset-standard` | 1.8.0 |
| `io.github.oshai:kotlin-logging` | 8.0.4 |
