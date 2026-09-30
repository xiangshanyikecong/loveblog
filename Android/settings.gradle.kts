pluginManagement {
    repositories {
        // Official repositories take precedence. The aliyun mirrors are kept
        // as a fallback for networks where dl.google.com is unreachable, but a
        // mirror must never shadow the canonical source: a compromised mirror
        // would otherwise resolve before the genuine artifact. Combined with
        // gradle/verification-metadata.xml this means a tampered dependency
        // fails the build even if it reaches the resolver first.
        google {
            content {
                includeGroupByRegex("com\\.android.*")
                includeGroupByRegex("com\\.google.*")
                includeGroupByRegex("androidx.*")
            }
        }
        mavenCentral()
        gradlePluginPortal()
        maven { url = uri("https://maven.aliyun.com/repository/google") }
        maven { url = uri("https://maven.aliyun.com/repository/gradle-plugin") }
        maven { url = uri("https://maven.aliyun.com/repository/public") }
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        maven { url = uri("https://maven.aliyun.com/repository/google") }
        maven { url = uri("https://maven.aliyun.com/repository/public") }
    }
}

rootProject.name = "LoveJournal"
include(":app")
