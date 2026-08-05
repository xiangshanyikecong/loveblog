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

package com.lovejournal.app.ui.cottage.vault

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.crypto.VaultCrypto
import com.lovejournal.app.data.crypto.VaultPlainEntry
import com.lovejournal.app.data.remote.dto.VaultEntryCreateRequest
import com.lovejournal.app.data.remote.dto.VaultEntryUpdateRequest
import com.lovejournal.app.data.remote.dto.VaultMetaResponse
import com.lovejournal.app.data.remote.dto.VaultRekeyEntry
import com.lovejournal.app.data.remote.dto.VaultRekeyRequest
import com.lovejournal.app.data.remote.dto.VaultSetupRequest
import com.lovejournal.app.data.repository.VaultRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.crypto.SecretKey
import javax.inject.Inject

data class VaultEntryUi(val vid: String, val title: String, val body: String, val updatedAt: String? = null)
data class VaultUiState(
    val loading: Boolean = true,
    val meta: VaultMetaResponse? = null,
    val unlocked: Boolean = false,
    val entries: List<VaultEntryUi> = emptyList(),
    val busy: Boolean = false,
    val message: String? = null,
)

@HiltViewModel
class VaultViewModel @Inject constructor(
    private val repository: VaultRepository,
    private val crypto: VaultCrypto,
) : ViewModel() {
    private val _state = MutableStateFlow(VaultUiState())
    val state: StateFlow<VaultUiState> = _state.asStateFlow()
    private var key: SecretKey? = null
    private var lockJob: Job? = null

    init { loadMeta() }

    fun loadMeta() = viewModelScope.launch {
        repository.meta().fold(
            onSuccess = { _state.value = _state.value.copy(loading = false, meta = it) },
            onFailure = { _state.value = _state.value.copy(loading = false, message = it.message ?: "加载失败") },
        )
    }

    fun setup(passphrase: String) {
        if (passphrase.length < 6) { message("口令至少 6 位"); return }
        _state.value = _state.value.copy(busy = true)
        viewModelScope.launch {
            runCatching {
                val salt = crypto.generateSalt()
                val derived = crypto.deriveKey(passphrase, salt, ITERATIONS)
                val verifier = crypto.createVerifier(derived)
                val meta = repository.setup(VaultSetupRequest(salt = salt, verifier_iv = verifier.iv, verifier_cipher = verifier.ciphertext)).getOrThrow()
                key = derived
                _state.value = _state.value.copy(meta = meta, unlocked = true, entries = emptyList(), busy = false)
                armAutoLock()
            }.onFailure { _state.value = _state.value.copy(busy = false, message = it.message ?: "创建失败") }
        }
    }

    fun unlock(passphrase: String) {
        val meta = _state.value.meta ?: return
        _state.value = _state.value.copy(busy = true)
        viewModelScope.launch {
            runCatching {
                val derived = crypto.deriveKey(passphrase, meta.salt ?: error("缺少盐值"), meta.iterations ?: ITERATIONS)
                if (!crypto.verify(derived, meta.verifier_iv ?: "", meta.verifier_cipher ?: "")) error("口令不正确")
                key = derived
                val entries = repository.entries().getOrThrow().map {
                    val plain = crypto.decryptEntry(derived, it.iv, it.ciphertext)
                    VaultEntryUi(it.vid, plain.title, plain.body, it.updated_at)
                }
                _state.value = _state.value.copy(unlocked = true, entries = entries, busy = false)
                armAutoLock()
            }.onFailure { _state.value = _state.value.copy(busy = false, message = it.message ?: "解锁失败") }
        }
    }

    fun save(vid: String?, title: String, body: String) {
        val currentKey = key ?: return
        if (title.isBlank() && body.isBlank()) { message("标题和内容不能都为空"); return }
        _state.value = _state.value.copy(busy = true)
        viewModelScope.launch {
            runCatching {
                val encrypted = crypto.encryptEntry(currentKey, VaultPlainEntry(title.trim(), body))
                val response = if (vid == null) repository.create(VaultEntryCreateRequest(encrypted.iv, encrypted.ciphertext)).getOrThrow()
                else repository.update(vid, VaultEntryUpdateRequest(encrypted.iv, encrypted.ciphertext)).getOrThrow()
                val item = VaultEntryUi(response.vid, title.trim(), body, response.updated_at)
                val items = _state.value.entries.filterNot { it.vid == response.vid }.toMutableList().apply { add(0, item) }
                _state.value = _state.value.copy(entries = items, busy = false, message = "已加密保存")
                armAutoLock()
            }.onFailure { _state.value = _state.value.copy(busy = false, message = it.message ?: "保存失败") }
        }
    }

    fun delete(vid: String) = viewModelScope.launch {
        repository.delete(vid).fold(
            onSuccess = { _state.value = _state.value.copy(entries = _state.value.entries.filterNot { it.vid == vid }); armAutoLock() },
            onFailure = { message(it.message ?: "删除失败") },
        )
    }

    fun changePassphrase(passphrase: String) {
        if (passphrase.length < 6) { message("新口令至少 6 位"); return }
        val currentEntries = _state.value.entries
        _state.value = _state.value.copy(busy = true)
        viewModelScope.launch {
            runCatching {
                val salt = crypto.generateSalt()
                val newKey = crypto.deriveKey(passphrase, salt, ITERATIONS)
                val verifier = crypto.createVerifier(newKey)
                val encrypted = currentEntries.map { entry ->
                    val value = crypto.encryptEntry(newKey, VaultPlainEntry(entry.title, entry.body))
                    VaultRekeyEntry(entry.vid, value.iv, value.ciphertext)
                }
                val meta = repository.rekey(VaultRekeyRequest(salt = salt, verifier_iv = verifier.iv, verifier_cipher = verifier.ciphertext, entries = encrypted)).getOrThrow()
                key = newKey
                _state.value = _state.value.copy(meta = meta, busy = false, message = "口令已更新")
                armAutoLock()
            }.onFailure { _state.value = _state.value.copy(busy = false, message = it.message ?: "改口令失败") }
        }
    }

    fun reset() = viewModelScope.launch {
        repository.reset().fold(
            onSuccess = { key = null; lockJob?.cancel(); _state.value = VaultUiState(loading = false, meta = VaultMetaResponse(false), message = "保险箱已重置") },
            onFailure = { message(it.message ?: "重置失败") },
        )
    }

    fun lock() { key = null; lockJob?.cancel(); _state.value = _state.value.copy(unlocked = false, entries = emptyList()) }
    fun touch() = armAutoLock()
    fun clearMessage() { _state.value = _state.value.copy(message = null) }
    private fun message(value: String) { _state.value = _state.value.copy(message = value) }
    private fun armAutoLock() { lockJob?.cancel(); lockJob = viewModelScope.launch { delay(5 * 60 * 1000L); lock(); message("保险箱已自动锁定") } }
    private companion object { const val ITERATIONS = 210000 }
}
