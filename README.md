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
