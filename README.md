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

Gradle Wrapper 自体は Dependabot の対象外です。更新するには次を実行します。

```bash
./gradlew wrapper --gradle-version <version>
```

## ローカルで確認する

```bash
./gradlew publishToMavenLocal
```

生成された `dependencyManagement` は次で確認できます。

```bash
cat ~/.m2/repository/com/github/asuka1975/kotlin-library-catalog/1.0.0-SNAPSHOT/kotlin-library-catalog-1.0.0-SNAPSHOT.pom
```

## GitHub / JitPack で公開する

Gradle Wrapper を含めてコミットし、タグを打ちます。

```bash
git add -A && git commit -m "Initial BOM"
git remote add origin git@github.com:asuka1975/kotlin-library-catalog.git
git push -u origin main
git tag v1.0.0 && git push origin v1.0.0
```

https://jitpack.io でリポジトリを Look up すると、JitPack が
`./gradlew build publishToMavenLocal` を実行して公開します。

座標はローカル発行時と JitPack で同じ形になります。

| | 座標 |
| --- | --- |
| ローカル (`mavenLocal`) | `com.github.asuka1975:kotlin-library-catalog:1.0.0-SNAPSHOT` |
| JitPack | `com.github.asuka1975:kotlin-library-catalog:v1.0.0` |

`group` / `version` は `gradle.properties` の値が使われ、JitPack 上では JitPack が
注入する `GROUP` / `VERSION` 環境変数で上書きされます。

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
    implementation(platform("com.github.asuka1975:kotlin-library-catalog:v1.0.0"))

    // バージョンを書かない
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core")
    implementation("io.ktor:ktor-client-cio")
    implementation("io.github.oshai:kotlin-logging")

    testImplementation("io.kotest:kotest-runner-junit5")
}
```

BOM 自体のバージョン（`v1.0.0`）は省略できません。

### バージョンを強制したい場合

`platform(...)` は「競合したらより高い方を選ぶ」ため、推移的依存によって BOM より
新しいバージョンが選ばれることがあります。BOM の値を強制するなら `enforcedPlatform(...)`
を使います。

```kotlin
implementation(enforcedPlatform("com.github.asuka1975:kotlin-library-catalog:v1.0.0"))
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

### 衝突したときの挙動

取り込んだ BOM と自前の `constraints` が同じライブラリを管理している場合、
**Gradle は高い方を選びます**（Maven の `dependencyManagement` は先勝ちなので挙動が違います）。
そのため、意図的に上書きするもの以外は重複させない方針にしています。

| ライブラリ | 管理元 | 備考 |
| --- | --- | --- |
| `kotlinx-coroutines-*` | 自前 (1.11.0) | Spring Boot は 1.10.2。意図的に上書き |
| `logback-classic` | Spring Boot (1.5.34) | ログ統合がバージョンに依存するため Spring Boot に委ねる |
| `slf4j-api` | Spring Boot (2.0.18) | 値が同じなので重複を持たない |

Spring Boot より新しいバージョンを使いたい場合は `constraints` に書き足せば上書きできます。
逆に Spring Boot の検証済みの組み合わせを厳密に守りたい場合は、自前の constraints を消してください。

## detekt / ktlint について

**Gradle プラグインのバージョンはこの BOM では統一できません。**
プラグインは buildscript / plugin classpath で解決され、そこはプロジェクトの
依存関係とは別のため、`platform(...)` の影響を受けないからです。

この BOM が効くのは、プロジェクトの依存として宣言するアーティファクトです。

```kotlin
dependencies {
    implementation(platform("com.github.asuka1975:kotlin-library-catalog:v1.0.0"))

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
| `org.jetbrains.kotlinx:kotlinx-coroutines-core` / `-test` | 1.11.0 |
| `org.jetbrains.kotlinx:kotlinx-serialization-json` | 1.11.0 |
| `org.jetbrains.kotlinx:kotlinx-datetime` | 0.8.0 |
| `io.ktor:ktor-client-core` / `-cio` / `-content-negotiation` / `ktor-serialization-kotlinx-json` | 3.5.1 |
| `io.kotest:kotest-runner-junit5` / `-assertions-core` / `-property` | 6.2.3 |
| `io.mockk:mockk` | 1.14.11 |
| `io.gitlab.arturbosch.detekt:detekt-formatting` / `-api` / `-cli` | 1.23.8 |
| `com.pinterest.ktlint:ktlint-cli` / `-rule-engine` / `-ruleset-standard` | 1.8.0 |
| `io.github.oshai:kotlin-logging` | 8.0.4 |
