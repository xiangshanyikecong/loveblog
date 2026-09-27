/*
 * Love Journal - a private journal + blog + real-time interaction platform for couples.
 * Copyright (C) 2026 Love Journal Contributors
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published
 * by the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

package com.lovejournal.app.push

import android.content.Context
import android.net.Uri
import com.google.firebase.FirebaseApp
import com.google.firebase.FirebaseOptions
import dagger.hilt.android.qualifiers.ApplicationContext
import java.io.File
import java.io.IOException
import javax.inject.Inject
import javax.inject.Singleton
import org.json.JSONArray
import org.json.JSONObject

/**
 * FCM 运行时配置：让自托管用户在应用内导入 google-services.json 即可启用
 * 推送，无需修改 gradle 重新构建（设计见 docs/design/FCM_IN_APP_SETUP_DESIGN.md）。
 *
 * 原理：gradle `google-services` 插件只是编译期把 json 变成资源再由
 * FirebaseInitProvider 自动初始化；Firebase 本身提供公开的手动初始化 API
 * [FirebaseApp.initializeApp]。PushRepository 的全部守卫都是
 * `FirebaseApp.getApps(context).isEmpty()`，运行时初始化成功后自动通过，
 * token 上报/接收链路零改动生效。
 *
 * 配置文件是公开的客户端配置（api_key 非机密），整体存入应用私有目录；
 * 真正敏感的服务端 service account 只在服务端 .env 中，与本类无关。
 */
@Singleton
class FirebaseRuntimeConfig @Inject constructor(
    @ApplicationContext private val context: Context,
) {
    @Volatile
    var lastInitError: String? = null
        private set

    val isInitialized: Boolean get() = FirebaseApp.getApps(context).isNotEmpty()

    val importedConfigExists: Boolean get() = configFile().exists()

    /**
     * 应用启动时调用：默认构建（无 google-services.json 资源）下，用应用内
     * 导入过的配置手动初始化。文件不存在或解析失败都静默返回（与未启用
     * 时的 no-op 姿态一致），失败原因记入 [lastInitError] 供诊断展示。
     */
    fun initializeFromPersistedConfig() {
        if (isInitialized) return
        val file = configFile()
        if (!file.exists()) return
        runCatching {
            FirebaseApp.initializeApp(context, parseOptions(file.readText()))
        }.onFailure { lastInitError = it.message }
    }

    /**
     * 应用内导入 google-services.json：解析校验 → 持久化到私有目录 → 立即
     * 初始化。先写文件再初始化，保证即使本次初始化失败，下次启动仍会重试。
     *
     * @throws IOException 无法读取所选文件
     * @throws IllegalArgumentException 文件内容不是有效的 google-services.json
     *         （缺少字段或包名不匹配，消息面向用户可直接展示）
     */
    fun importConfig(uri: Uri) {
        val text = context.contentResolver.openInputStream(uri)?.use { stream ->
            stream.readBytes().decodeToString()
        } ?: throw IOException("无法读取所选文件")
        val options = parseOptions(text)
        configFile().writeText(text)
        lastInitError = null
        val app = FirebaseApp.initializeApp(context, options)
        if (app == null && !isInitialized) {
            throw IllegalStateException("Firebase 初始化失败，请重试")
        }
    }

    /** 移除导入的配置并注销当前进程内的 Firebase 实例（设置页「移除推送配置」）。 */
    fun removeImportedConfig() {
        configFile().delete()
        FirebaseApp.getApps(context).forEach { app ->
            runCatching { app.delete() }
        }
    }

    private fun configFile(): File = File(context.filesDir, "firebase_config.json")

    /**
     * 解析并校验 google-services.json。校验规则：必须是本应用的包名
     * （用户常选错 Firebase 项目），applicationId / api_key / 项目号齐备。
     */
    private fun parseOptions(text: String): FirebaseOptions {
        val root = runCatching { JSONObject(text) }
            .getOrElse { throw IllegalArgumentException("不是有效的 JSON 配置文件，请选择 Firebase 控制台下载的 google-services.json") }
        val projectInfo = root.optJSONObject("project_info")
            ?: throw IllegalArgumentException("文件缺少 project_info，请确认选择的是 google-services.json")
        val clients: JSONArray = root.optJSONArray("client")
            ?: throw IllegalArgumentException("文件缺少 client 配置，请确认选择的是 google-services.json")

        val packageName = context.packageName
        val client = (0 until clients.length())
            .mapNotNull { clients.optJSONObject(it) }
            .firstOrNull { candidate ->
                candidate.optJSONObject("client_info")
                    ?.optJSONObject("android_client_info")
                    ?.optString("package_name") == packageName
            }
            ?: throw IllegalArgumentException("所选配置的包名不是 $packageName，请确认在 Firebase 控制台添加的是本应用（Android 包名需完全一致）")

        val clientInfo = client.optJSONObject("client_info")
            ?: throw IllegalArgumentException("文件缺少 client_info")
        val applicationId = clientInfo.optString("mobilesdk_app_id")
        if (applicationId.isBlank()) {
            throw IllegalArgumentException("配置缺少 mobilesdk_app_id，请重新从 Firebase 控制台下载")
        }
        val apiKey = client.optJSONArray("api_key")?.optJSONObject(0)?.optString("current_key").orEmpty()
        if (apiKey.isBlank()) {
            throw IllegalArgumentException("配置缺少 api_key，请重新从 Firebase 控制台下载")
        }
        val senderId = projectInfo.optString("project_number")
        if (senderId.isBlank()) {
            throw IllegalArgumentException("配置缺少 project_number（推送发送方 ID），请重新下载")
        }

        val builder = FirebaseOptions.Builder()
            .setApplicationId(applicationId)
            .setApiKey(apiKey)
            .setGcmSenderId(senderId)
        val projectId = projectInfo.optString("project_id")
        if (projectId.isNotBlank()) builder.setProjectId(projectId)
        val storageBucket = projectInfo.optString("storage_bucket")
        if (storageBucket.isNotBlank()) builder.setStorageBucket(storageBucket)
        return builder.build()
    }
}
