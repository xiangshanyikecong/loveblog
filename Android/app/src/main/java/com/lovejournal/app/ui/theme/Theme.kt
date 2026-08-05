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

package com.lovejournal.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.ui.graphics.Color
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.material3.Shapes
import androidx.compose.runtime.Composable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.unit.dp

private val LightColors = lightColorScheme(
    primary = LovePink,
    onPrimary = LoveOnPrimary,
    onPrimaryContainer = LoveText,
    primaryContainer = LovePinkLight,
    secondary = LovePinkDark,
    tertiary = LoveLavender,
    background = LoveBackground,
    surface = LoveSurface,
    surfaceVariant = Color(0xFFFFEEF3),
    outline = LoveOutline,
    onBackground = LoveText,
    onSurface = LoveText,
    onSurfaceVariant = Color(0xFF6B5A60),
)

private val DarkColors = darkColorScheme(
    primary = LovePinkDarkScheme,
    onPrimary = LoveBackgroundDark,
    onPrimaryContainer = Color(0xFFFFEEF3),
    primaryContainer = Color(0xFF6B3F4D),
    secondary = LovePinkLight,
    tertiary = Color(0xFFC8BFFF),
    background = LoveBackgroundDark,
    surface = LoveSurfaceDark,
    surfaceVariant = Color(0xFF33262B),
    outline = Color(0xFF5A4A52),
    onBackground = Color(0xFFFFEEF3),
    onSurface = Color(0xFFFFEEF3),
    onSurfaceVariant = Color(0xFFC8B8C0),
    error = Color(0xFFFFB4AB),
    errorContainer = Color(0xFF93000A),
    onError = LoveBackgroundDark,
)

private val LoveShapes = Shapes(
    extraSmall = RoundedCornerShape(10.dp),
    small = RoundedCornerShape(14.dp),
    medium = RoundedCornerShape(20.dp),
    large = RoundedCornerShape(28.dp),
    extraLarge = RoundedCornerShape(34.dp),
)

@Composable
fun LoveJournalTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colors = if (darkTheme) DarkColors else LightColors
    MaterialTheme(
        colorScheme = colors,
        typography = LoveTypography,
        shapes = LoveShapes,
        content = content,
    )
}
