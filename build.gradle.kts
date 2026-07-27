plugins {
    `java-platform`
    `maven-publish`
}

// JitPack はビルドに GROUP / ARTIFACT / VERSION を環境変数として渡します。
// ローカルでは gradle.properties の値がそのまま使われます。
System.getenv("GROUP")?.takeIf { it.isNotBlank() }?.let { group = it }
System.getenv("VERSION")?.takeIf { it.isNotBlank() }?.let { version = it }

// バージョンを共有するライブラリ群
val coroutines = "1.11.0"
val serialization = "1.11.0"
val ktor = "3.5.1"
val kotest = "6.2.3"

// 他の BOM を取り込みたい場合のみ有効にしてください（下の api(platform(...)) と併用）。
// javaPlatform {
//     allowDependencies()
// }

dependencies {
    // 外部 BOM の取り込み例（allowDependencies() が必要）
    // api(platform("org.jetbrains.kotlin:kotlin-bom:2.4.10"))

    // ここに書いたバージョンが、利用側でこのライブラリが使われたときに適用されます。
    // 依存として追加されるわけではないので、使わないものが混ざっていても害はありません。
    constraints {
        // Kotlin 公式ライブラリ
        api("org.jetbrains.kotlinx:kotlinx-coroutines-core:$coroutines")
        api("org.jetbrains.kotlinx:kotlinx-coroutines-test:$coroutines")
        api("org.jetbrains.kotlinx:kotlinx-serialization-json:$serialization")
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

        // ロギング
        api("io.github.oshai:kotlin-logging:8.0.4")
        api("ch.qos.logback:logback-classic:1.6.0")
        api("org.slf4j:slf4j-api:2.0.18")
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
