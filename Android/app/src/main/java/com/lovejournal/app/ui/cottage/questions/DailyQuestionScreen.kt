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

package com.lovejournal.app.ui.cottage.questions

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.lovejournal.app.data.remote.dto.DailyQuestionAnswerDto
import com.lovejournal.app.data.remote.dto.DailyQuestionResponse
import com.lovejournal.app.ui.components.LovePage

@Composable
fun DailyQuestionScreen(viewModel: DailyQuestionViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    val message by viewModel.message.collectAsStateWithLifecycle()

    LovePage {
    Column(modifier = Modifier.fillMaxSize()) {
        message?.let {
            Text(
                text = it,
                color = MaterialTheme.colorScheme.primary,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 4.dp),
            )
        }
        when {
            state.loading && state.question == null ->
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            state.error != null && state.question == null ->
                Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Text("加载失败：${state.error}", color = MaterialTheme.colorScheme.error)
                }
            state.question == null -> CreateQuestion(
                submitting = state.submitting,
                onCreate = viewModel::createToday,
            )
            else -> QuestionContent(
                question = state.question!!,
                submitting = state.submitting,
                onAnswer = viewModel::answer,
            )
        }
    }
    }
}

@Composable
private fun CreateQuestion(submitting: Boolean, onCreate: (String) -> Unit) {
    var prompt by remember { mutableStateOf("") }
    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text("今天还没有问题", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
        Text("写下一个想问 TA 的问题，发布后两人各自作答，都答完才会一起揭晓。", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        OutlinedTextField(
            value = prompt,
            onValueChange = { prompt = it },
            label = { Text("今天想问 TA…") },
            modifier = Modifier.fillMaxWidth(),
        )
        Button(
            onClick = { onCreate(prompt) },
            enabled = !submitting,
            modifier = Modifier.fillMaxWidth(),
        ) { Text("发布今天的问题") }
    }
}

@Composable
private fun QuestionContent(
    question: DailyQuestionResponse,
    submitting: Boolean,
    onAnswer: (String) -> Unit,
) {
    val self = question.answers.firstOrNull { it.is_self }
    var draft by remember(question.qid) { mutableStateOf("") }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(16.dp)) {
                Text(question.question_date, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.outline)
                Spacer(Modifier.height(4.dp))
                Text(question.prompt, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            }
        }

        question.answers.forEach { AnswerCard(it, question.revealed) }

        if (self == null || !self.answered) {
            OutlinedTextField(
                value = draft,
                onValueChange = { draft = it },
                label = { Text("写下你的回答") },
                modifier = Modifier.fillMaxWidth(),
            )
            Button(
                onClick = { onAnswer(draft) },
                enabled = !submitting,
                modifier = Modifier.fillMaxWidth(),
            ) { Text("提交回答") }
        } else if (!question.revealed) {
            Text(
                "你已作答，等 TA 答完就能一起看啦 💌",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.primary,
            )
        }
    }
}

@Composable
private fun AnswerCard(answer: DailyQuestionAnswerDto, revealed: Boolean) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.padding(14.dp)) {
            Text(
                answer.author_nickname + if (answer.is_self) "（我）" else "",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.primary,
            )
            Spacer(Modifier.height(4.dp))
            val body = when {
                answer.content_visible && answer.content != null -> answer.content
                answer.answered && !revealed -> "已作答 · 待揭晓"
                answer.answered -> "已作答"
                else -> "还没有回答"
            }
            Text(body, style = MaterialTheme.typography.bodyMedium)
        }
    }
}
