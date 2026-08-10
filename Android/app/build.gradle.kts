import org.gradle.api.artifacts.ResolvedArtifact

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.android)
    alias(libs.plugins.kotlin.serialization)
    alias(libs.plugins.ksp)
    alias(libs.plugins.hilt)
}

val sourceCodeUrl = providers.gradleProperty("SOURCE_CODE_URL")
    .orElse("https://github.com/xiangshanyikecong/loveblog")
    .get()
val sourceCodeUrlLiteral = "\"${sourceCodeUrl.replace("\\", "\\\\").replace("\"", "\\\"")}\""

android {
    namespace = "com.lovejournal.app"
    compileSdk = 36
    buildToolsVersion = "36.1.0"

    defaultConfig {
        applicationId = "com.lovejournal.app"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "1.0.1"

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        vectorDrawables { useSupportLibrary = true }

        buildConfigField("String", "API_BASE_URL", "\"https://love.invalid/api/v1/\"")
        buildConfigField("String", "MEDIA_BASE_URL", "\"https://love.invalid\"")
        buildConfigField("String", "SOURCE_CODE_URL", sourceCodeUrlLiteral)
        buildConfigField("boolean", "ALLOW_CLEARTEXT_LOCAL", "false")
    }

    buildTypes {
        debug {
            isMinifyEnabled = false
            // Installing a debug build is the explicit opt-in for local HTTP.
            buildConfigField("String", "API_BASE_URL", "\"http://10.0.2.2:8000/v1/\"")
            buildConfigField("String", "MEDIA_BASE_URL", "\"http://10.0.2.2:8000\"")
            buildConfigField("boolean", "ALLOW_CLEARTEXT_LOCAL", "true")
        }
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    composeOptions {
        kotlinCompilerExtensionVersion = "1.5.14"
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.ktx)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.activity.compose)

    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.ui)
    implementation(libs.androidx.ui.graphics)
    implementation(libs.androidx.ui.tooling.preview)
    implementation(libs.androidx.material3)
    implementation(libs.androidx.material.icons.extended)
    debugImplementation(libs.androidx.ui.tooling)

    implementation(libs.androidx.navigation.compose)

    implementation(libs.hilt.android)
    ksp(libs.hilt.compiler)
    implementation(libs.androidx.hilt.navigation.compose)
    implementation(libs.androidx.hilt.work)
    ksp(libs.androidx.hilt.compiler)

    implementation(libs.retrofit)
    implementation(libs.retrofit.kotlinx.serialization)
    implementation(libs.okhttp)
    implementation(libs.okhttp.logging)
    implementation(libs.kotlinx.serialization.json)

    implementation(libs.room.runtime)
    implementation(libs.room.ktx)
    ksp(libs.room.compiler)

    implementation(libs.androidx.datastore.preferences)
    implementation(libs.androidx.work.runtime.ktx)
    implementation(libs.kotlinx.coroutines.android)

    implementation(libs.androidx.security.crypto)

    implementation(libs.androidx.media3.exoplayer)
    implementation(libs.androidx.media3.ui)
    implementation(libs.androidx.media3.datasource.okhttp)

    implementation(libs.androidx.glance.appwidget)
    implementation(libs.androidx.glance.material3)

    implementation(libs.coil.compose)

    implementation(platform(libs.firebase.bom))
    implementation(libs.firebase.messaging)

    testImplementation("junit:junit:4.13.2")
}

tasks.register("exportReleaseLicenseInventory") {
    group = "reporting"
    description = "Exports resolved release runtime artifacts for third-party notice generation."

    val outputFile = layout.buildDirectory.file("reports/license-inventory/release-runtime-artifacts.json")
    outputs.file(outputFile)

    doLast {
        fun json(value: String): String = buildString {
            append('"')
            value.forEach { character ->
                when (character) {
                    '\\' -> append("\\\\")
                    '"' -> append("\\\"")
                    '\n' -> append("\\n")
                    '\r' -> append("\\r")
                    '\t' -> append("\\t")
                    else -> append(character)
                }
            }
            append('"')
        }

        val artifacts = configurations.getByName("releaseRuntimeClasspath")
            .resolvedConfiguration
            .resolvedArtifacts
            .filter { artifact: ResolvedArtifact -> artifact.moduleVersion.id.group.isNotBlank() }
            .sortedWith(
                compareBy<ResolvedArtifact>(
                    { it.moduleVersion.id.group },
                    { it.moduleVersion.id.name },
                    { it.moduleVersion.id.version },
                ),
            )
            .distinctBy { artifact ->
                val id = artifact.moduleVersion.id
                "${id.group}:${id.name}:${id.version}"
            }

        val lines = artifacts.map { artifact ->
            val id = artifact.moduleVersion.id
            "    {\"group\": ${json(id.group)}, \"module\": ${json(id.name)}, " +
                "\"version\": ${json(id.version)}, \"file\": ${json(artifact.file.absolutePath)}}"
        }
        val content = buildString {
            appendLine("{")
            appendLine("  \"schema_version\": 1,")
            appendLine("  \"variant\": \"release\",")
            appendLine("  \"configuration\": \"releaseRuntimeClasspath\",")
            appendLine("  \"artifacts\": [")
            append(lines.joinToString(",\n"))
            appendLine()
            appendLine("  ]")
            appendLine("}")
        }
        val file = outputFile.get().asFile
        file.parentFile.mkdirs()
        file.writeText(content)
    }
}
