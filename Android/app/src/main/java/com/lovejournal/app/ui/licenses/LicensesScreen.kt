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

package com.lovejournal.app.ui.licenses

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.selection.SelectionContainer
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material3.Button
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.dp
import com.lovejournal.app.BuildConfig
import com.lovejournal.app.R
import com.lovejournal.app.ui.components.LovePage
import com.lovejournal.app.ui.components.LoveSectionTitle
import com.lovejournal.app.ui.components.LoveSoftCard

@Composable
fun LicensesScreen() {
    val context = LocalContext.current
    val uriHandler = LocalUriHandler.current
    val documentContents = remember(context) {
        listOf(
            context.resources.openRawResource(R.raw.agpl_3_0).bufferedReader().use { it.readText() },
            context.resources.openRawResource(R.raw.notice).bufferedReader().use { it.readText() },
            context.resources.openRawResource(R.raw.third_party_licenses).bufferedReader().use { it.readText() },
        )
    }
    val documentLabels = listOf(
        stringResource(R.string.licenses_project_license),
        stringResource(R.string.licenses_copyright),
        stringResource(R.string.licenses_full_license),
    )
    var selectedDocument by remember { mutableIntStateOf(0) }

    LovePage {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            LoveSectionTitle(
                stringResource(R.string.licenses_title),
                stringResource(R.string.licenses_subtitle),
            )
            Column(
                modifier = Modifier.fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                documentLabels.forEachIndexed { index, label ->
                    if (selectedDocument == index) {
                        Button(
                            onClick = { selectedDocument = index },
                            modifier = Modifier.fillMaxWidth(),
                        ) { Text(label) }
                    } else {
                        OutlinedButton(
                            onClick = { selectedDocument = index },
                            modifier = Modifier.fillMaxWidth(),
                        ) { Text(label) }
                    }
                }
            }
            OutlinedButton(
                onClick = { uriHandler.openUri(BuildConfig.SOURCE_CODE_URL) },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Icon(imageVector = Icons.AutoMirrored.Filled.OpenInNew, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text(stringResource(R.string.licenses_source_code))
            }
            LoveSoftCard(Modifier.fillMaxWidth()) {
                SelectionContainer {
                    Text(
                        text = documentContents[selectedDocument],
                        modifier = Modifier.padding(16.dp),
                        style = MaterialTheme.typography.bodySmall,
                        fontFamily = FontFamily.Monospace,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}
