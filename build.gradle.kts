plugins {
    `java-platform`
    `maven-publish`
}

// JitPack はビルドに GROUP / ARTIFACT / VERSION を環境変数として渡します。
// ローカルでは gradle.properties の値がそのまま使われます。
System.getenv("GROUP")?.takeIf { it.isNotBlank() }?.let { group = it }
System.getenv("VERSION")?.takeIf { it.isNotBlank() }?.let { version = it }

// バージョンを共有するライブラリ群
val springBoot = "4.1.0"
val ktor = "3.5.1"
val kotest = "6.2.4"
val detekt = "1.23.8"
val ktlint = "1.8.0"

// 他の BOM を取り込むために必要
javaPlatform {
    allowDependencies()
}

dependencies {
    // Spring Boot が管理する 648 件（Spring / Jackson / Logback / JUnit など）を取り込む。
    // 取り込んだ BOM と下の constraints が衝突した場合、Gradle は高い方を選ぶ。
    api(platform("org.springframework.boot:spring-boot-dependencies:$springBoot"))

    // ここに書いたバージョンが、利用側でこのライブラリが使われたときに適用されます。
    // 依存として追加されるわけではないので、使わないものが混ざっていても害はありません。
    constraints {
        // Kotlin 公式ライブラリ
        // kotlin / kotlinx-coroutines / kotlinx-serialization は Spring Boot が
        // それぞれの BOM を import しているので、そちらの管理に任せる。
        // kotlinx-datetime は Spring Boot の管理対象外なのでここで指定する。
        api("org.jetbrains.kotlinx:kotlinx-datetime:0.8.0")

        // Ktor
        api("io.ktor:ktor-client-core:$ktor")
        api("io.ktor:ktor-client-cio:$ktor")
        api("io.ktor:ktor-client-content-negotiation:$ktor")
        api("io.ktor:ktor-serialization-kotlinx-json:$ktor")

        // テスト
        api("io.kotest:kotest-runner-junit5:$kotest")
        api("io.kotest:kotest-assertions-core:$kotest")
        api("io.kotest:kotest-property:$kotest")
        api("io.mockk:mockk:1.14.11")

        // 静的解析 / フォーマッタ
        // detekt-formatting は detektPlugins 構成で使う
        api("io.gitlab.arturbosch.detekt:detekt-formatting:$detekt")
        api("io.gitlab.arturbosch.detekt:detekt-api:$detekt")
        api("io.gitlab.arturbosch.detekt:detekt-cli:$detekt")
        api("com.pinterest.ktlint:ktlint-cli:$ktlint")
        api("com.pinterest.ktlint:ktlint-rule-engine:$ktlint")
        api("com.pinterest.ktlint:ktlint-ruleset-standard:$ktlint")

        // ロギング
        // logback-classic / slf4j-api は Spring Boot 側の管理に任せる
        // （Spring Boot はログ統合が logback のバージョンに依存するため）
        api("io.github.oshai:kotlin-logging:8.0.4")
    }
}

publishing {
    publications {
        create<MavenPublication>("bom") {
            from(components["javaPlatform"])

            pom {
                name = "kotlin-library-catalog"
                description = "共有ライブラリのバージョンを統一する BOM"
            }
        }
    }
}
