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

package com.lovejournal.app.ui.cottage.games.canvas

import android.graphics.Bitmap
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.lovejournal.app.data.prefs.SessionManager
import com.lovejournal.app.data.remote.dto.CanvasArtworkResponse
import com.lovejournal.app.data.repository.CanvasRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import java.io.File
import java.io.FileOutputStream
import java.util.UUID
import javax.inject.Inject

data class CanvasSegment(
    val sid: String,
    val x0: Float, val y0: Float,
    val x1: Float, val y1: Float,
    val color: String,
    val size: Float,
    val eraser: Boolean,
)

data class CanvasStroke(
    val sid: String,
    val mine: Boolean,
    val segs: List<CanvasSegment>,
)

data class RemoteCursor(
    val x: Float,
    val y: Float,
    val visible: Boolean,
)

data class CanvasUiState(
    val connected: Boolean = false,
    val selfUid: String? = null,
    val partnerOnline: Boolean = false,
    val strokes: List<CanvasStroke> = emptyList(),
    val remoteCursor: RemoteCursor = RemoteCursor(0f, 0f, false),
    val color: String = "#1e293b",
    val size: Float = 4f,
    val eraser: Boolean = false,
    val saving: Boolean = false,
    // True while we're persisting a snapshot to the artwork gallery.
    val savingToGallery: Boolean = false,
)

@HiltViewModel
class CanvasViewModel @Inject constructor(
    private val repository: CanvasRepository,
    session: SessionManager,
) : ViewModel() {

    private val _state = MutableStateFlow(CanvasUiState())
    val state: StateFlow<CanvasUiState> = _state.asStateFlow()

    private val _toast = MutableSharedFlow<String>(extraBufferCapacity = 4)
    val toast: SharedFlow<String> = _toast

    private val outBuffer = mutableListOf<CanvasSegment>()
    private var flushJob: Job? = null
    private var lastCursorSent = 0L

    init {
        viewModelScope.launch {
            _state.value = _state.value.copy(selfUid = session.sessionFlow.first().uid)
        }
        viewModelScope.launch {
            repository.connected.collect { connected ->
                _state.value = _state.value.copy(connected = connected)
                if (connected) {
                    repository.send("""{"type":"SYNC_REQUEST","payload":{}}""")
                }
            }
        }
        viewModelScope.launch {
            repository.events.collect(::handleEvent)
        }
        repository.connect()
    }

    private fun handleEvent(event: JsonObject) {
        val type = event["type"]?.jsonPrimitive?.contentOrNull ?: return
        val payload = event["payload"]?.jsonObject
        val fromUid = event["from_uid"]?.jsonPrimitive?.contentOrNull

        when (type) {
            "STROKE" -> {
                val segs = payload?.get("segs")?.jsonArray ?: return
                val segments = segs.mapNotNull { elem ->
                    val obj = elem.jsonObject
                    val sid = obj["sid"]?.jsonPrimitive?.contentOrNull ?: return@mapNotNull null
                    CanvasSegment(
                        sid = sid,
                        x0 = obj["x0"]?.jsonPrimitive?.doubleOrNull?.toFloat() ?: 0f,
                        y0 = obj["y0"]?.jsonPrimitive?.doubleOrNull?.toFloat() ?: 0f,
                        x1 = obj["x1"]?.jsonPrimitive?.doubleOrNull?.toFloat() ?: 0f,
                        y1 = obj["y1"]?.jsonPrimitive?.doubleOrNull?.toFloat() ?: 0f,
                        color = obj["color"]?.jsonPrimitive?.contentOrNull ?: "#1e293b",
                        size = obj["size"]?.jsonPrimitive?.doubleOrNull?.toFloat() ?: 4f,
                        eraser = obj["eraser"]?.jsonPrimitive?.booleanOrNull ?: false,
                    )
                }
                if (segments.isEmpty()) return
                val mine = fromUid == _state.value.selfUid
                appendSegments(segments, mine)
            }
            "CLEAR" -> _state.value = _state.value.copy(strokes = emptyList())
            "UNDO" -> {
                val sid = payload?.get("sid")?.jsonPrimitive?.contentOrNull ?: return
                _state.value = _state.value.copy(strokes = _state.value.strokes.filter { it.sid != sid })
            }
            "CURSOR" -> {
                val p = payload ?: return
                if (p["leave"]?.jsonPrimitive?.booleanOrNull == true) {
                    _state.value = _state.value.copy(remoteCursor = RemoteCursor(0f, 0f, false))
                } else {
                    val x = p["x"]?.jsonPrimitive?.doubleOrNull?.toFloat() ?: return
                    val y = p["y"]?.jsonPrimitive?.doubleOrNull?.toFloat() ?: return
                    _state.value = _state.value.copy(remoteCursor = RemoteCursor(x, y, true))
                }
            }
            "SYNC_REQUEST" -> {
                val syncPayload = buildSyncPayload()
                if (syncPayload.isNotEmpty()) repository.send(syncPayload)
            }
            "SYNC" -> {
                val strokesList = payload?.get("strokes")?.jsonArray ?: return
                val allStrokes = strokesList.mapNotNull { elem ->
                    val obj = elem.jsonObject
                    val sid = obj["sid"]?.jsonPrimitive?.contentOrNull ?: return@mapNotNull null
                    val segs = obj["segs"]?.jsonArray?.mapNotNull { segElem ->
                        val segObj = segElem.jsonObject
                        CanvasSegment(
                            sid = sid,
                            x0 = segObj["x0"]?.jsonPrimitive?.doubleOrNull?.toFloat() ?: 0f,
                            y0 = segObj["y0"]?.jsonPrimitive?.doubleOrNull?.toFloat() ?: 0f,
                            x1 = segObj["x1"]?.jsonPrimitive?.doubleOrNull?.toFloat() ?: 0f,
                            y1 = segObj["y1"]?.jsonPrimitive?.doubleOrNull?.toFloat() ?: 0f,
                            color = segObj["color"]?.jsonPrimitive?.contentOrNull ?: "#1e293b",
                            size = segObj["size"]?.jsonPrimitive?.doubleOrNull?.toFloat() ?: 4f,
                            eraser = segObj["eraser"]?.jsonPrimitive?.booleanOrNull ?: false,
                        )
                    } ?: emptyList()
                    CanvasStroke(sid = sid, mine = false, segs = segs)
                }
                _state.value = _state.value.copy(strokes = allStrokes)
            }
            "PRESENCE_SNAPSHOT" -> {
                val online = payload?.get("online")?.jsonArray
                    ?.mapNotNull { it.jsonPrimitive?.contentOrNull } ?: emptyList()
                val self = _state.value.selfUid
                _state.value = _state.value.copy(partnerOnline = online.any { it != self })
            }
            "PRESENCE" -> {
                val uid = payload?.get("uid")?.jsonPrimitive?.contentOrNull ?: return
                val online = payload["online"]?.jsonPrimitive?.booleanOrNull ?: return
                if (uid != _state.value.selfUid) {
                    _state.value = _state.value.copy(partnerOnline = online)
                }
            }
        }
    }

    private fun appendSegments(segments: List<CanvasSegment>, mine: Boolean) {
        val current = _state.value.strokes.toMutableList()
        for (seg in segments) {
            val existing = current.indexOfFirst { it.sid == seg.sid }
            if (existing >= 0) {
                current[existing] = current[existing].copy(segs = current[existing].segs + seg)
            } else {
                current.add(CanvasStroke(sid = seg.sid, mine = mine, segs = listOf(seg)))
            }
        }
        _state.value = _state.value.copy(strokes = current)
    }

    fun newSid(): String = UUID.randomUUID().toString().take(12)

    fun onStrokeStart(x: Float, y: Float, sid: String) {
        val s = _state.value
        val seg = CanvasSegment(sid, x, y, x, y, if (s.eraser) "#ffffff" else s.color, s.size, s.eraser)
        appendSegments(listOf(seg), mine = true)
        bufferOutgoing(seg)
    }

    fun onStrokeMove(x: Float, y: Float, sid: String, lastX: Float, lastY: Float) {
        val s = _state.value
        val seg = CanvasSegment(sid, lastX, lastY, x, y, if (s.eraser) "#ffffff" else s.color, s.size, s.eraser)
        appendSegments(listOf(seg), mine = true)
        bufferOutgoing(seg)
    }

    private fun bufferOutgoing(seg: CanvasSegment) {
        outBuffer.add(seg)
        if (flushJob == null || flushJob?.isCompleted == true) {
            flushJob = viewModelScope.launch {
                while (isActive && outBuffer.isNotEmpty()) {
                    delay(16)
                    flush()
                }
            }
        }
    }

    private fun flush() {
        if (outBuffer.isEmpty()) return
        val segs = outBuffer.toList()
        outBuffer.clear()
        val segsJson = segs.joinToString(",") { seg ->
            """{"sid":"${seg.sid}","x0":${seg.x0},"y0":${seg.y0},"x1":${seg.x1},"y1":${seg.y1},"color":"${seg.color}","size":${seg.size},"eraser":${seg.eraser}}"""
        }
        repository.send("""{"type":"STROKE","payload":{"segs":[$segsJson]}}""")
    }

    fun clear() {
        _state.value = _state.value.copy(strokes = emptyList())
        repository.send("""{"type":"CLEAR","payload":{}}""")
    }

    fun undo() {
        val strokes = _state.value.strokes
        val idx = strokes.indexOfLast { it.mine }
        if (idx < 0) return
        val removed = strokes[idx]
        _state.value = _state.value.copy(strokes = strokes.filterIndexed { i, _ -> i != idx })
        repository.send("""{"type":"UNDO","payload":{"sid":"${removed.sid}"}}""")
        if (outBuffer.isNotEmpty()) flush()
    }

    fun onCursorMove(x: Float, y: Float) {
        val now = System.currentTimeMillis()
        if (now - lastCursorSent < 40) return
        lastCursorSent = now
        repository.send("""{"type":"CURSOR","payload":{"x":$x,"y":$y}}""")
    }

    fun onCursorLeave() {
        repository.send("""{"type":"CURSOR","payload":{"leave":true,"x":-1,"y":-1}}""")
    }

    fun setColor(color: String) {
        _state.value = _state.value.copy(color = color, eraser = false)
    }

    fun setSize(size: Float) {
        _state.value = _state.value.copy(size = size)
    }

    fun toggleEraser() {
        _state.value = _state.value.copy(eraser = !_state.value.eraser)
    }

    /**
     * Snapshot the current board and POST it to the gallery endpoint.
     * The same JSON shape is what the web frontend stores, so a saved
     * artwork can be replayed on either platform.
     *
     * Returns the persisted artwork so callers can update UI / navigate.
     */
    fun saveToGallery(
        cacheDir: File,
        title: String? = null,
    ) {
        viewModelScope.launch {
            _state.value = _state.value.copy(savingToGallery = true)
            try {
                val bitmap = renderBitmap()
                val file = File(cacheDir, "canvas-gallery-${System.currentTimeMillis()}.png")
                FileOutputStream(file).use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
                val part = MultipartBody.Part.createFormData(
                    "file", file.name,
                    file.asRequestBody("image/png".toMediaTypeOrNull()),
                )
                val upload = withContext(Dispatchers.IO) {
                    repository.uploadTimelineImage(part).getOrThrow()
                }
                val strokesJson = buildStrokesJson()
                val idempotencyKey = UUID.randomUUID().toString()
                val created = withContext(Dispatchers.IO) {
                    repository.createArtwork(
                        title = title?.takeIf { it.isNotBlank() },
                        strokesJson = strokesJson,
                        thumbDataUrl = upload.url,
                        width = 960,
                        height = 600,
                        idempotencyKey = idempotencyKey,
                    ).getOrThrow()
                }
                _toast.tryEmit("已保存到作品集（${created.collaborators.size} 位合作者）")
            } catch (e: Exception) {
                _toast.tryEmit("保存失败: ${e.message}")
            } finally {
                _state.value = _state.value.copy(savingToGallery = false)
            }
        }
    }

    /** Serialised snapshot of the strokes — mirrors SharedCanvas.getStrokesJson() on web. */
    fun buildStrokesJson(): String {
        val obj = kotlinx.serialization.json.buildJsonObject {
            put("width", kotlinx.serialization.json.JsonPrimitive(960))
            put("height", kotlinx.serialization.json.JsonPrimitive(600))
            put("strokes", kotlinx.serialization.json.buildJsonArray {
                for (stroke in _state.value.strokes) {
                    add(
                        kotlinx.serialization.json.buildJsonObject {
                            put("sid", kotlinx.serialization.json.JsonPrimitive(stroke.sid))
                            put(
                                "segs",
                                kotlinx.serialization.json.buildJsonArray {
                                    for (seg in stroke.segs) {
                                        add(
                                            kotlinx.serialization.json.buildJsonObject {
                                                put("sid", kotlinx.serialization.json.JsonPrimitive(seg.sid))
                                                put("x0", kotlinx.serialization.json.JsonPrimitive(seg.x0))
                                                put("y0", kotlinx.serialization.json.JsonPrimitive(seg.y0))
                                                put("x1", kotlinx.serialization.json.JsonPrimitive(seg.x1))
                                                put("y1", kotlinx.serialization.json.JsonPrimitive(seg.y1))
                                                put("color", kotlinx.serialization.json.JsonPrimitive(seg.color))
                                                put("size", kotlinx.serialization.json.JsonPrimitive(seg.size))
                                                put("eraser", kotlinx.serialization.json.JsonPrimitive(seg.eraser))
                                            },
                                        )
                                    }
                                },
                            )
                        },
                    )
                }
            })
        }
        return obj.toString()
    }

    fun saveToTimeline(cacheDir: File) {
        viewModelScope.launch {
            _state.value = _state.value.copy(saving = true)
            try {
                val bitmap = renderBitmap()
                val file = File(cacheDir, "canvas-${System.currentTimeMillis()}.png")
                FileOutputStream(file).use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
                val part = MultipartBody.Part.createFormData(
                    "file", file.name,
                    file.asRequestBody("image/png".toMediaTypeOrNull()),
                )
                val upload = withContext(Dispatchers.IO) { repository.uploadTimelineImage(part) }
                upload.getOrThrow()
                withContext(Dispatchers.IO) {
                    repository.createMoment("我们一起画的", listOf(upload.getOrThrow().url))
                }.getOrThrow()
                _toast.tryEmit("已保存到时间轴")
                file.delete()
            } catch (e: Exception) {
                _toast.tryEmit("保存失败: ${e.message}")
            } finally {
                _state.value = _state.value.copy(saving = false)
            }
        }
    }

    fun renderBitmap(): Bitmap {
        val width = 960
        val height = 600
        val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        val canvas = android.graphics.Canvas(bitmap)
        canvas.drawColor(android.graphics.Color.WHITE)
        val paint = android.graphics.Paint().apply {
            isAntiAlias = true
            strokeCap = android.graphics.Paint.Cap.ROUND
            strokeJoin = android.graphics.Paint.Join.ROUND
            style = android.graphics.Paint.Style.STROKE
        }
        for (stroke in _state.value.strokes) {
            for (seg in stroke.segs) {
                paint.color = try {
                    android.graphics.Color.parseColor(seg.color)
                } catch (_: Exception) {
                    android.graphics.Color.parseColor("#1e293b")
                }
                paint.strokeWidth = seg.size
                if (seg.eraser) {
                    paint.xfermode = android.graphics.PorterDuffXfermode(android.graphics.PorterDuff.Mode.CLEAR)
                } else {
                    paint.xfermode = null
                }
                canvas.drawLine(seg.x0 * width, seg.y0 * height, seg.x1 * width, seg.y1 * height, paint)
            }
        }
        return bitmap
    }

    private fun buildSyncPayload(): String {
        val strokes = _state.value.strokes
        if (strokes.isEmpty()) return ""
        val strokesJson = strokes.joinToString(",") { stroke ->
            val segsJson = stroke.segs.joinToString(",") { seg ->
                """{"sid":"${seg.sid}","x0":${seg.x0},"y0":${seg.y0},"x1":${seg.x1},"y1":${seg.y1},"color":"${seg.color}","size":${seg.size},"eraser":${seg.eraser}}"""
            }
            """{"sid":"${stroke.sid}","segs":[$segsJson]}"""
        }
        return """{"type":"SYNC","payload":{"strokes":[$strokesJson]}}"""
    }

    override fun onCleared() {
        flushJob?.cancel()
        repository.disconnect()
        super.onCleared()
    }
}