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

## 他の BOM を取り込む

`build.gradle.kts` の `javaPlatform { allowDependencies() }` と `api(platform(...))` の
コメントを外すと、既存の BOM をこの BOM に取り込めます。

```kotlin
javaPlatform {
    allowDependencies()
}

dependencies {
    api(platform("org.jetbrains.kotlin:kotlin-bom:2.4.10"))
}
```

## 管理しているライブラリ

| ライブラリ | バージョン |
| --- | --- |
| `org.jetbrains.kotlinx:kotlinx-coroutines-core` / `-test` | 1.11.0 |
| `org.jetbrains.kotlinx:kotlinx-serialization-json` | 1.11.0 |
| `org.jetbrains.kotlinx:kotlinx-datetime` | 0.8.0 |
| `io.ktor:ktor-client-core` / `-cio` / `-content-negotiation` / `ktor-serialization-kotlinx-json` | 3.5.1 |
| `io.kotest:kotest-runner-junit5` / `-assertions-core` / `-property` | 6.2.3 |
| `io.mockk:mockk` | 1.14.11 |
| `io.github.oshai:kotlin-logging` | 8.0.4 |
| `ch.qos.logback:logback-classic` | 1.6.0 |
| `org.slf4j:slf4j-api` | 2.0.18 |
