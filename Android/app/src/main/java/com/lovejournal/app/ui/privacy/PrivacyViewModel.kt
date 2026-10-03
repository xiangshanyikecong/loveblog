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

package com.lovejournal.app.ui.privacy

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.R
import com.lovejournal.app.data.remote.api.LoveApiService
import com.lovejournal.app.ui.components.UiText
import com.lovejournal.app.ui.components.toUiText
import com.lovejournal.app.ui.components.uiText
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import javax.inject.Inject

data class PrivacyUiState(
    val loading: Boolean = true,
    val error: UiText? = null,
    val generatedAt: String? = null,
    val accountNickname: String = "",
    val lastLogin: String = "",
    val lastLoginIp: String = "",
    val passwordChangedAt: String = "",
    val sessionVersion: String = "",
    val totalsPublic: String = "",
    val totalsSignedIn: String = "",
    val totalsPartners: String = "",
    val totalsAuthorOnly: String = "",
    val totalsPassword: String = "",
    val encryptionRows: List<Pair<String, UiText>> = emptyList(),
    val exportEncrypted: UiText = uiText(R.string.privacy_no),
    val exportUploads: UiText = uiText(R.string.privacy_no),
    val exportServerReadable: UiText = uiText(R.string.privacy_no),
    val exportE2eeCipher: UiText = uiText(R.string.privacy_no),
    val recentActivity: List<String> = emptyList(),
)

/** 隐私中心：把 /v1/privacy/summary 摊开给人看（只读）。 */
@HiltViewModel
class PrivacyViewModel @Inject constructor(
    private val api: LoveApiService,
) : ViewModel() {

    private val _state = MutableStateFlow(PrivacyUiState())
    val state: StateFlow<PrivacyUiState> = _state.asStateFlow()

    init { refresh() }

    fun refresh() {
        viewModelScope.launch {
            _state.value = _state.value.copy(loading = true, error = null)
            runCatching { api.privacySummary() }
                .onSuccess { json -> _state.value = parse(json) }
                .onFailure { _state.value = _state.value.copy(loading = false, error = it.toUiText()) }
        }
    }

    private fun parse(root: JsonObject): PrivacyUiState {
        fun JsonObject.str(path: String): String =
            path.split('.').fold(this as kotlinx.serialization.json.JsonElement?) { acc, key ->
                (acc as? JsonObject)?.get(key)
            }?.jsonPrimitive?.contentOrNull ?: ""

        fun JsonObject.int(path: String): String = str(path).ifBlank { "0" }

        val encryption = runCatching {
            root["encryption"]?.jsonArray?.map { el ->
                val obj = el.jsonObject
                val label = obj.str("label")
                val initialized = obj.str("initialized") == "true"
                val items = obj.str("item_count")
                val encrypted = obj.str("encrypted_count")
                label to if (initialized && items.isNotBlank()) {
                    uiText(R.string.privacy_encryption_enabled_items, items, encrypted)
                } else {
                    uiText(if (initialized) R.string.privacy_enabled else R.string.privacy_disabled)
                }
            } ?: emptyList()
        }.getOrDefault(emptyList())

        val activity = runCatching {
            root["recent_activity"]?.jsonArray?.take(5)?.map { el ->
                val obj = el.jsonObject
                buildString {
                    append(obj.str("created_at").take(16).replace('T', ' '))
                    append("  ")
                    append(obj.str("action"))
                    if (obj.str("resource_name").isNotBlank()) append(" · ${obj.str("resource_name")}")
                }
            } ?: emptyList()
        }.getOrDefault(emptyList())

        return PrivacyUiState(
            loading = false,
            generatedAt = root.str("generated_at"),
            accountNickname = root.str("account.nickname"),
            lastLogin = root.str("account.last_login_at"),
            lastLoginIp = root.str("account.last_login_ip"),
            passwordChangedAt = root.str("account.password_changed_at"),
            sessionVersion = root.int("account.session_version"),
            totalsPublic = root.int("totals.public"),
            totalsSignedIn = root.int("totals.signed_in"),
            totalsPartners = root.int("totals.partners"),
            totalsAuthorOnly = root.int("totals.author_only"),
            totalsPassword = root.int("totals.password"),
            encryptionRows = encryption,
            exportEncrypted = if (root.str("export_policy.archive_encrypted").ifBlank { "false" } == "true") uiText(R.string.privacy_yes) else uiText(R.string.privacy_no),
            exportUploads = if (root.str("export_policy.uploads_included").ifBlank { "false" } == "true") uiText(R.string.privacy_yes) else uiText(R.string.privacy_no),
            exportServerReadable = if (root.str("export_policy.server_readable_content_plaintext").ifBlank { "false" } == "true") uiText(R.string.privacy_yes) else uiText(R.string.privacy_no),
            exportE2eeCipher = if (root.str("export_policy.end_to_end_content_plaintext").ifBlank { "false" } == "true") uiText(R.string.privacy_yes) else uiText(R.string.privacy_no),
            recentActivity = activity,
        )
    }
}
