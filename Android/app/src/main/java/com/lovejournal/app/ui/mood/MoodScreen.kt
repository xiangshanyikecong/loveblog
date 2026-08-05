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

package com.lovejournal.app.ui.mood

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import com.lovejournal.app.data.local.entity.MoodEntity
import com.lovejournal.app.media.MediaCapture
import com.lovejournal.app.ui.components.LovePage

private val MOODS = listOf(
    "开心" to "😄",
    "幸福" to "🥰",
    "平静" to "😌",
    "想你" to "🥺",
    "难过" to "😢",
    "生气" to "😠",
)

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun MoodScreen(viewModel: MoodViewModel = hiltViewModel()) {
    val context = LocalContext.current
    val moods by viewModel.moods.collectAsStateWithLifecycle()
    val status by viewModel.status.collectAsStateWithLifecycle()
    val attachment by viewModel.attachmentUrl.collectAsStateWithLifecycle()
    val snackbar = remember { SnackbarHostState() }

    var selected by remember { mutableStateOf(MOODS.first()) }
    var note by remember { mutableStateOf("") }
    var cameraUri by remember { mutableStateOf<Uri?>(null) }

    val galleryLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.PickVisualMedia(),
    ) { uri -> uri?.let { viewModel.uploadPhoto(it) } }

    val cameraLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.TakePicture(),
    ) { success -> if (success) cameraUri?.let { viewModel.uploadPhoto(it) } }

    LaunchedEffect(status) {
        status?.let {
            snackbar.showSnackbar(it)
            viewModel.clearStatus()
        }
    }

    Scaffold(snackbarHost = { SnackbarHost(snackbar) }) { padding ->
        LovePage(modifier = Modifier.padding(padding)) {
            LazyColumn(
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
            item { Text("今天心情怎么样？", style = MaterialTheme.typography.titleMedium) }
            item {
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    MOODS.forEach { entry ->
                        FilterChip(
                            selected = selected == entry,
                            onClick = { selected = entry },
                            label = { Text("${entry.second} ${entry.first}") },
                        )
                    }
                }
            }
            item {
                OutlinedTextField(
                    value = note,
                    onValueChange = { note = it },
                    label = { Text("想说的话（可选）") },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = {
                        val uri = MediaCapture.newImageUri(context)
                        cameraUri = uri
                        cameraLauncher.launch(uri)
                    }) { Text("拍照") }
                    OutlinedButton(onClick = {
                        galleryLauncher.launch(
                            PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly),
                        )
                    }) { Text("从相册选择") }
                }
            }
            if (attachment != null) {
                item {
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(
                            "已附带图片",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.primary,
                        )
                        AsyncImage(
                            model = viewModel.mediaUrl(attachment),
                            contentDescription = "已附带图片",
                            contentScale = ContentScale.Crop,
                            modifier = Modifier
                                .size(96.dp)
                                .clip(RoundedCornerShape(8.dp)),
                        )
                    }
                }
            }
            item {
                Button(
                    onClick = {
                        val noteWithPhoto = buildString {
                            append(note)
                            attachment?.let { if (note.isNotBlank()) append('\n'); append(it) }
                        }.ifBlank { null }
                        viewModel.checkIn(selected.first, selected.second, noteWithPhoto)
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("打卡") }
            }
            item {
                Spacer(Modifier.height(8.dp))
                Text("最近心情", style = MaterialTheme.typography.titleMedium)
            }
            items(moods, key = { it.mid }) { MoodRow(it, viewModel::mediaUrl) }
        }
    }
    }
}

/**
 * Splits a mood note into its text body and an optional attached image path.
 * Photos are appended to the note as a trailing line (the backend mood schema
 * has no dedicated image field), so we render that line as an actual image
 * instead of dumping a raw URL as text.
 */
private fun splitNote(note: String?): Pair<String?, String?> {
    if (note.isNullOrBlank()) return null to null
    val lines = note.lines()
    val imageLine = lines.lastOrNull { line ->
        val t = line.trim()
        t.startsWith("/uploads") || t.startsWith("http://") || t.startsWith("https://")
    }
    if (imageLine == null) return note to null
    val text = lines.filterNot { it == imageLine }.joinToString("\n").trim().ifBlank { null }
    return text to imageLine.trim()
}

@Composable
private fun MoodRow(mood: MoodEntity, mediaUrl: (String?) -> String?) {
    val (text, imagePath) = splitNote(mood.note)
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(modifier = Modifier.padding(12.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(mood.emoji ?: "🙂", style = MaterialTheme.typography.headlineSmall)
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("${mood.authorNickname} · ${mood.mood}", style = MaterialTheme.typography.titleSmall)
                Text(mood.moodDate, style = MaterialTheme.typography.bodySmall)
                text?.let { Text(it, style = MaterialTheme.typography.bodyMedium) }
                imagePath?.let {
                    AsyncImage(
                        model = mediaUrl(it),
                        contentDescription = "心情图片",
                        contentScale = ContentScale.Crop,
                        modifier = Modifier
                            .size(140.dp)
                            .clip(RoundedCornerShape(10.dp)),
                    )
                }
            }
        }
    }
}
