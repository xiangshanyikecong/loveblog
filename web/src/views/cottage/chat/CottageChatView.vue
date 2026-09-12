<!--
  Love Journal - a private journal + blog + real-time interaction platform for couples.
  Copyright (C) 2026 Love Journal Contributors

  This program is free software: you can redistribute it and/or modify
  it under the terms of the GNU Affero General Public License as published
  by the Free Software Foundation, version 3 of the License.

  This program is distributed in the hope that it will be useful,
  but WITHOUT ANY WARRANTY; without even the implied warranty of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
  GNU Affero General Public License for more details.

  You should have received a copy of the GNU Affero General Public License
  along with this program.  If not, see <https://www.gnu.org/licenses/>.
-->

<template>
  <div class="content-section chat-shell">
    <header class="chat-header glass-card">
      <router-link to="/cottage" class="chat-icon-btn chat-back" :aria-label="t('cottageChat.backToCottage')" :title="t('cottageChat.backToCottage')">
        <ArrowLeft :size="20" :stroke-width="2" aria-hidden="true" />
      </router-link>
      <div class="chat-peer">
        <div class="chat-peer-avatar" :class="{ online: partner.online }">
          {{ initialOf(partner.nickname) }}
          <span class="chat-peer-dot" :class="{ online: partner.online }"></span>
        </div>
        <div class="chat-peer-meta">
          <p class="chat-peer-name">{{ partner.nickname || t('cottageChat.noPartner') }}</p>
          <p class="chat-peer-status" :class="{ online: partner.online || partnerTyping.isTyping }">
            {{ partnerStatusText }}
          </p>
        </div>
      </div>
      <div class="chat-header-actions" :aria-label="t('cottageChat.quickActions')">
        <button
          class="chat-icon-btn chat-security-btn"
          type="button"
          :title="chatE2EEnabled ? (chatE2EUnlocked ? t('cottageChat.e2eEnabledTitle') : t('cottageChat.e2eLockedTitle')) : t('cottageChat.e2eSetupTitle')"
          :aria-label="chatE2EEnabled ? (chatE2EUnlocked ? t('cottageChat.e2eEnabledTitle') : t('cottageChat.e2eLockedAria')) : t('cottageChat.e2eSetupTitle')"
          :class="{
            enabled: chatE2EEnabled && chatE2EUnlocked,
            locked: chatE2EEnabled && !chatE2EUnlocked,
          }"
          @click="openE2EDialog"
        >
          <LockKeyholeOpen v-if="chatE2EEnabled && chatE2EUnlocked" :size="18" :stroke-width="2" aria-hidden="true" />
          <LockKeyhole v-else :size="18" :stroke-width="2" aria-hidden="true" />
        </button>
        <button
          v-for="p in pokes"
          :key="p.kind"
          class="chat-icon-btn chat-nudge-btn"
          type="button"
          :disabled="pokeBusy"
          :title="p.label"
          :aria-label="p.label"
          @click="poke(p.kind)"
        >
          <span class="chat-nudge-emoji" aria-hidden="true">{{ p.emoji }}</span>
        </button>
      </div>
    </header>

    <section class="chat-tools glass-card" :class="{ open: toolsOpen }">
      <button
        type="button"
        class="chat-tools-toggle"
        :aria-expanded="toolsOpen"
        aria-controls="chat-tools-drawer"
        @click="toolsOpen = !toolsOpen"
      >
        <span class="chat-tools-icon" aria-hidden="true">
          <Archive :size="19" :stroke-width="2" />
        </span>
        <span class="chat-tools-copy">
          <strong>{{ t('cottageChat.toolsTitle') }}</strong>
          <span>{{ toolsSummary }}</span>
        </span>
        <ChevronDown class="chat-tools-chevron" :size="19" :stroke-width="2" aria-hidden="true" />
      </button>

      <transition name="tools-expand">
        <div v-if="toolsOpen" id="chat-tools-drawer" class="chat-tools-drawer">
          <div class="chat-tool-tabs" role="tablist" :aria-label="t('cottageChat.toolsTabsAria')">
            <button
              type="button"
              role="tab"
              :aria-selected="activeTool === 'pinned'"
              :class="{ active: activeTool === 'pinned' }"
              @click="activeTool = 'pinned'"
            >
              <Pin :size="17" :stroke-width="2" aria-hidden="true" />
              <span>{{ t('cottageChat.tabPinned') }}</span>
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeTool === 'memory'"
              :class="{ active: activeTool === 'memory' }"
              @click="activeTool = 'memory'"
            >
              <ChartNoAxesColumnIncreasing :size="17" :stroke-width="2" aria-hidden="true" />
              <span>{{ t('cottageChat.tabToday') }}</span>
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeTool === 'future'"
              :class="{ active: activeTool === 'future' }"
              @click="activeTool = 'future'"
            >
              <CalendarClock :size="17" :stroke-width="2" aria-hidden="true" />
              <span>{{ t('cottageChat.tabFuture') }}</span>
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeTool === 'media'"
              :class="{ active: activeTool === 'media' }"
              @click="activeTool = 'media'"
            >
              <Images :size="17" :stroke-width="2" aria-hidden="true" />
              <span>{{ t('cottageChat.tabMedia') }}</span>
            </button>
            <button
              type="button"
              role="tab"
              :aria-selected="activeTool === 'search'"
              :class="{ active: activeTool === 'search' }"
              @click="activeTool = 'search'"
            >
              <Search :size="17" :stroke-width="2" aria-hidden="true" />
              <span>{{ t('cottageChat.tabSearch') }}</span>
            </button>
          </div>

          <div class="chat-tool-content" role="tabpanel">
            <article v-if="activeTool === 'pinned'" class="chat-tool-pane">
              <div class="chat-panel-head">
                <div>
                  <h3>{{ t('cottageChat.pinnedHeading') }}</h3>
                </div>
                <button
                  v-if="pinnedQuote"
                  type="button"
                  class="chat-mini-btn"
                  :disabled="pinBusy"
                  @click="clearPinned"
                >
                  {{ t('cottageChat.unpin') }}
                </button>
              </div>
              <blockquote v-if="pinnedQuote" class="chat-quote">
                <p>"{{ messageSnippet(pinnedQuote) }}"</p>
                <footer>{{ pinnedQuote.sender_nickname }}，{{ formatDayTime(pinnedQuote.created_at) }}</footer>
              </blockquote>
              <p v-else class="chat-panel-empty">{{ t('cottageChat.pinnedEmpty') }}</p>
            </article>

            <article v-else-if="activeTool === 'memory'" class="chat-tool-pane">
              <div class="chat-panel-head">
                <div>
                  <h3>{{ t('cottageChat.memoryHeading') }}</h3>
                </div>
                <button
                  type="button"
                  class="chat-icon-btn chat-refresh-btn"
                  :disabled="panelLoading"
                  :aria-label="t('cottageChat.refreshMemoryAria')"
                  :title="t('cottageChat.refresh')"
                  @click="loadPanels()"
                >
                  <RefreshCw :size="17" :stroke-width="2" aria-hidden="true" />
                </button>
              </div>
              <div class="chat-memory-grid">
                <div class="chat-memory-stat">
                  <span class="chat-memory-value">{{ memoryCard?.total_messages || 0 }}</span>
                  <span class="chat-memory-label">{{ t('cottageChat.statMessages') }}</span>
                </div>
                <div class="chat-memory-stat">
                  <span class="chat-memory-value">{{ memoryCard?.favorite_count || 0 }}</span>
                  <span class="chat-memory-label">{{ t('cottageChat.statFavorites') }}</span>
                </div>
                <div class="chat-memory-stat">
                  <span class="chat-memory-value">{{ memoryCard?.self_messages || 0 }}</span>
                  <span class="chat-memory-label">{{ t('cottageChat.statMine') }}</span>
                </div>
                <div class="chat-memory-stat">
                  <span class="chat-memory-value">{{ memoryCard?.partner_messages || 0 }}</span>
                  <span class="chat-memory-label">{{ t('cottageChat.statPartner') }}</span>
                </div>
              </div>
              <div class="chat-memory-lines">
                <p>
                  <span>{{ t('cottageChat.firstMessage') }}</span>
                  <strong>{{ memoryCard?.first_message ? messageSnippet(memoryCard.first_message) : t('cottageChat.noChatHistory') }}</strong>
                </p>
                <p>
                  <span>{{ t('cottageChat.lastMessage') }}</span>
                  <strong>{{ memoryCard?.last_message ? messageSnippet(memoryCard.last_message) : t('cottageChat.noChatHistory') }}</strong>
                </p>
              </div>
              <div class="chat-keywords">
                <span v-for="item in keywordItems" :key="item.keyword" class="chat-keyword-chip">
                  #{{ item.keyword }} {{ item.count }}
                </span>
                <span v-if="!keywordItems.length" class="chat-panel-empty">{{ t('cottageChat.noKeywords') }}</span>
              </div>
            </article>

            <article v-else-if="activeTool === 'future'" class="chat-tool-pane">
              <div class="chat-panel-head">
                <div>
                  <h3>{{ t('cottageChat.futureHeading') }}</h3>
                </div>
                <button v-if="futureAtInput" type="button" class="chat-mini-btn" @click="clearFutureSchedule">
                  {{ t('cottageChat.clearTime') }}
                </button>
              </div>
              <label class="chat-schedule-field">
                <span>{{ t('cottageChat.appearTime') }}</span>
                <input v-model="futureAtInput" type="datetime-local" class="chat-datetime" />
              </label>
              <p v-if="futureAtInput" class="chat-schedule-hint">
                {{ t('cottageChat.futureHint', { time: formatLocalInputValue(futureAtInput) }) }}
              </p>
              <div v-if="futureMessages.length" class="chat-future-list">
                <div v-for="item in futureMessages" :key="item.mid" class="chat-future-item">
                  <p class="chat-future-text">{{ messageSnippet(item) }}</p>
                  <p class="chat-future-meta">{{ formatDayTime(item.visible_at) }}</p>
                </div>
              </div>
              <p v-else class="chat-panel-empty">{{ t('cottageChat.noFutureMessages') }}</p>
            </article>

            <article v-else-if="activeTool === 'media'" class="chat-tool-pane">
              <div class="chat-panel-head">
                <div>
                  <h3>{{ t('cottageChat.mediaHeading') }}</h3>
                </div>
                <button
                  type="button"
                  class="chat-icon-btn chat-refresh-btn"
                  :disabled="panelLoading"
                  :aria-label="t('cottageChat.refreshMediaAria')"
                  :title="t('cottageChat.refresh')"
                  @click="loadPanels()"
                >
                  <RefreshCw :size="17" :stroke-width="2" aria-hidden="true" />
                </button>
              </div>
              <div class="chat-media-sections">
                <section class="chat-media-group">
                  <div class="chat-media-head"><span>{{ t('cottageChat.mediaImages') }}</span><strong>{{ mediaPanel.images.length }}</strong></div>
                  <div v-if="mediaPanel.images.length" class="chat-media-grid">
                    <button v-for="item in mediaPanel.images" :key="item.mid" type="button" class="chat-media-thumb" @click="previewImage(item.media_url)">
                      <img :src="resolveAssetUrl(item.media_url)" :alt="t('cottageChat.altChatImage')" />
                    </button>
                  </div>
                  <p v-else class="chat-panel-empty">{{ t('cottageChat.noImages') }}</p>
                </section>
                <section class="chat-media-group">
                  <div class="chat-media-head"><span>{{ t('cottageChat.mediaStickers') }}</span><strong>{{ mediaPanel.stickers.length }}</strong></div>
                  <div v-if="mediaPanel.stickers.length" class="chat-media-grid">
                    <button v-for="item in mediaPanel.stickers" :key="item.mid" type="button" class="chat-media-thumb" @click="previewImage(item.media_url)">
                      <img :src="resolveAssetUrl(item.media_url)" :alt="t('cottageChat.altChatSticker')" />
                    </button>
                  </div>
                  <p v-else class="chat-panel-empty">{{ t('cottageChat.noStickers') }}</p>
                </section>
                <section class="chat-media-group">
                  <div class="chat-media-head"><span>{{ t('cottageChat.mediaVoices') }}</span><strong>{{ mediaPanel.voices.length }}</strong></div>
                  <div v-if="mediaPanel.voices.length" class="chat-media-voices">
                    <div v-for="item in mediaPanel.voices" :key="item.mid" class="chat-media-voice">
                      <audio :src="resolveAssetUrl(item.media_url)" controls preload="metadata" class="chat-audio"></audio>
                      <span>{{ formatSeconds(item.audio_duration_sec) }}</span>
                    </div>
                  </div>
                  <p v-else class="chat-panel-empty">{{ t('cottageChat.noVoices') }}</p>
                </section>
                <section class="chat-media-group">
                  <div class="chat-media-head"><span>{{ t('cottageChat.mediaFavorites') }}</span><strong>{{ mediaPanel.favorites.length }}</strong></div>
                  <div v-if="mediaPanel.favorites.length" class="chat-media-favorites">
                    <button v-for="item in mediaPanel.favorites" :key="item.mid" type="button" class="chat-favorite-item" @click="openMessageFromTools(item.mid)">
                      <span>{{ item.sender_nickname || t('cottageChat.them') }}</span>
                      <strong>{{ messageSnippet(item) }}</strong>
                    </button>
                  </div>
                  <p v-else class="chat-panel-empty">{{ t('cottageChat.noFavorites') }}</p>
                </section>
              </div>
            </article>

            <article v-else class="chat-tool-pane">
              <div class="chat-panel-head">
                <div>
                  <h3>{{ t('cottageChat.searchHeading') }}</h3>
                </div>
              </div>
              <div class="chat-search-box">
                <input
                  v-model="searchQuery"
                  type="text"
                  class="input chat-search-input"
                  :placeholder="t('cottageChat.searchPlaceholder')"
                  @input="onSearchInput"
                />
                <LoaderCircle v-if="searchBusy" class="chat-search-spin" :size="16" :stroke-width="2" aria-hidden="true" />
              </div>
              <p v-if="chatE2EEnabled && chatE2EUnlocked" class="chat-search-hint">
                {{ t('cottageChat.searchEncryptedHint') }}
              </p>
              <p v-else-if="chatE2EEnabled && !chatE2EUnlocked" class="chat-search-hint">
                {{ t('cottageChat.searchLockedHint') }}
              </p>
              <div v-if="searchResults.length" class="chat-search-results">
                <button
                  v-for="item in searchResults"
                  :key="item.mid"
                  type="button"
                  class="chat-search-result"
                  @click="openSearchResult(item.mid)"
                >
                  <span class="chat-search-result-who">{{ item.is_self ? t('cottageChat.me') : (item.sender_nickname || t('cottageChat.them')) }}</span>
                  <strong class="chat-search-result-text">{{ messageSnippet(item) }}</strong>
                  <span class="chat-search-result-time">{{ formatDayTime(item.created_at) }}</span>
                </button>
              </div>
              <p v-else-if="searchSearched && !searchBusy" class="chat-panel-empty">{{ t('cottageChat.noSearchResults') }}</p>
              <p v-else class="chat-panel-empty">{{ t('cottageChat.searchInitialHint') }}</p>
            </article>
          </div>
        </div>
      </transition>
    </section>

    <section class="chat-room glass-card" :aria-label="t('cottageChat.roomAria')">
      <div ref="listEl" class="chat-list" @scroll="onScroll">
      <div class="chat-load-more">
        <button v-if="hasMore" class="chat-load-btn" :disabled="loadingOlder" @click="loadOlder">
          {{ loadingOlder ? t('cottageChat.loadingMore') : t('cottageChat.loadOlder') }}
        </button>
        <span v-else-if="messages.length" class="chat-load-hint">{{ t('cottageChat.chatStartHint') }}</span>
      </div>

      <div v-if="loading" class="chat-skeleton" role="status" aria-label="正在加载悄悄话">
        <span></span>
        <span></span>
        <span></span>
      </div>
      <div v-else-if="!messages.length" class="chat-empty">
        <MessageCircleHeart :size="28" :stroke-width="1.8" aria-hidden="true" />
        <strong>{{ t('cottageChat.noMessagesTitle') }}</strong>
        <span>{{ t('cottageChat.noMessagesDesc') }}</span>
      </div>

      <template v-for="(m, idx) in messages" :key="m.mid">
        <div v-if="dayDividerIndices.has(idx)" class="chat-day">{{ formatDay(m.created_at) }}</div>
        <div v-if="showUnreadDivider(m)" class="chat-unread-divider">{{ t('cottageChat.unreadDivider') }}</div>
        <div class="chat-row" :class="{ self: m.is_self }" :data-mid="m.mid">
          <div v-if="!m.is_self" class="chat-bubble-avatar">{{ initialOf(m.sender_nickname) }}</div>
          <div class="chat-bubble-wrap">
            <div class="chat-bubble" :class="{ self: m.is_self, media: isMediaBubble(m), recalled: m.is_recalled }">
              <div v-if="m.is_favorite || (pinnedQuote && pinnedQuote.mid === m.mid)" class="chat-bubble-marks">
                <span v-if="m.is_favorite" class="chat-favorite-mark">
                  <Star :size="12" :stroke-width="2" aria-hidden="true" />
                  {{ t('cottageChat.favorited') }}
                </span>
                <span v-if="pinnedQuote && pinnedQuote.mid === m.mid" class="chat-pinned-mark">
                  <Pin :size="12" :stroke-width="2" aria-hidden="true" />
                  {{ t('cottageChat.pinnedMark') }}
                </span>
              </div>
              <div v-if="m.reply_to" class="chat-reply-preview" :class="{ self: m.is_self }">
                <span class="chat-reply-author">{{ m.reply_to.sender_nickname || t('cottageChat.them') }}</span>
                <span class="chat-reply-text">{{ replySnippet(m.reply_to) }}</span>
              </div>
              <div v-if="m.is_recalled" class="chat-recalled-text">
                {{ recalledLabel(m) }}
              </div>
              <div
                v-else-if="m.is_encrypted && m._decryption_failed"
                class="chat-encrypted-placeholder"
              >
                <LockKeyhole :size="16" :stroke-width="2" aria-hidden="true" />
                <span>{{ t('cottageChat.encryptedLocked') }}</span>
              </div>
              <div
                v-else-if="m.is_encrypted && m.type === 'text' && m.content == null"
                class="chat-encrypted-placeholder"
              >
                <LockKeyhole :size="16" :stroke-width="2" aria-hidden="true" />
                <span>{{ t('cottageChat.decrypting') }}</span>
              </div>
              <div
                v-else-if="m.is_encrypted && m.type !== 'text' && !mediaSrc(m)"
                class="chat-encrypted-placeholder"
              >
                <LockKeyhole :size="16" :stroke-width="2" aria-hidden="true" />
                <span>{{ t('cottageChat.decrypting') }}</span>
              </div>
              <img
                v-else-if="m.type === 'image' || m.type === 'sticker'"
                :src="mediaSrc(m)"
                class="chat-image"
                :alt="m.type === 'sticker' ? '贴纸' : '图片'"
                @click="previewImage(mediaSrc(m))"
                @load="onImageLoad"
              />
              <div v-else-if="m.type === 'voice'" class="chat-voice-bubble">
                <audio :src="mediaSrc(m)" controls preload="metadata" class="chat-audio"></audio>
                <span class="chat-voice-duration">{{ formatSeconds(m.audio_duration_sec) }}</span>
              </div>
              <span v-else class="chat-text">{{ m.content }}</span>
            </div>
            <div class="chat-meta" :class="{ self: m.is_self }">
              <span class="chat-time">{{ formatTime(m.created_at) }}</span>
              <span v-if="m.is_self" class="chat-receipt" :class="{ read: m.read_at }">
                {{ m.read_at ? "已读" : "已送达" }}
              </span>
            </div>
            <div class="chat-actions" :class="{ self: m.is_self }">
              <button
                type="button"
                class="chat-action-btn"
                :disabled="!!actionBusyMid"
                :title="t('cottageChat.replyTitle')"
                :aria-label="t('cottageChat.replyAria')"
                @click="replyToMessage(m)"
              >
                <Reply :size="14" :stroke-width="2" aria-hidden="true" />
              </button>
              <button
                type="button"
                class="chat-action-btn"
                :disabled="actionBusyMid === m.mid || m.is_recalled"
                :title="m.is_favorite ? t('cottageChat.unfavoriteTitle') : t('cottageChat.favoriteTitle')"
                :aria-label="m.is_favorite ? t('cottageChat.unfavoriteAria') : t('cottageChat.favoriteAria')"
                @click="toggleFavorite(m)"
              >
                <Star :size="14" :stroke-width="2" :fill="m.is_favorite ? 'currentColor' : 'none'" aria-hidden="true" />
              </button>
              <button
                v-if="m.type === 'text' && m.content && !m.is_recalled"
                type="button"
                class="chat-action-btn"
                :disabled="pinBusy"
                :title="pinnedQuote && pinnedQuote.mid === m.mid ? t('cottageChat.pinnedAlreadyTitle') : t('cottageChat.pinQuoteTitle')"
                :aria-label="pinnedQuote && pinnedQuote.mid === m.mid ? t('cottageChat.pinnedAlreadyAria') : t('cottageChat.pinQuoteAria')"
                @click="pinQuote(m)"
              >
                <Pin :size="14" :stroke-width="2" aria-hidden="true" />
              </button>
              <button
                v-if="canRecallMessage(m)"
                type="button"
                class="chat-action-btn"
                :disabled="actionBusyMid === m.mid"
                :title="t('cottageChat.recallTitle')"
                :aria-label="t('cottageChat.recallAria')"
                @click="recallMessage(m)"
              >
                <Undo2 :size="14" :stroke-width="2" aria-hidden="true" />
              </button>
            </div>
          </div>
        </div>
      </template>
    </div>

      <form class="chat-input" @submit.prevent="send">
      <div v-if="replyingTo" class="chat-reply-bar">
        <div>
          <span>{{ t('cottageChat.replyBarText', { name: replyingTo.sender_nickname || t('cottageChat.them') }) }}</span>
          <strong>{{ messageSnippet(replyingTo) }}</strong>
        </div>
        <button type="button" class="chat-icon-btn chat-close-btn" :aria-label="t('cottageChat.cancelReplyAria')" :title="t('cottageChat.cancelReplyAria')" @click="clearReply">
          <X :size="16" :stroke-width="2" aria-hidden="true" />
        </button>
      </div>
      <div v-if="futureAtInput" class="chat-send-tip">
        {{ t('cottageChat.futureSendTip', { time: formatLocalInputValue(futureAtInput) }) }}
      </div>
      <div v-if="voiceDraft" class="chat-voice-draft">
        <div class="chat-voice-draft-main">
          <span class="chat-voice-pill">{{ voiceDraft.source === "record" ? t('cottageChat.voiceRecorded') : t('cottageChat.voiceSelected') }}</span>
          <strong>{{ formatSeconds(voiceDraft.durationSec) }}</strong>
        </div>
        <audio :src="voiceDraft.previewUrl" controls preload="metadata" class="chat-audio"></audio>
        <button type="button" class="chat-mini-btn" @click="clearVoiceDraft">{{ t('cottageChat.removeVoice') }}</button>
      </div>
      <div class="chat-input-row">
        <label class="chat-attach-btn" :class="{ busy: uploading }" :title="t('cottageChat.sendImageAria')" :aria-label="t('cottageChat.sendImageAria')">
          <input type="file" accept="image/*" hidden @change="onPickImage" />
          <ImagePlus v-if="!uploading" :size="19" :stroke-width="2" aria-hidden="true" />
          <LoaderCircle v-else class="chat-loading-icon" :size="18" :stroke-width="2" aria-hidden="true" />
        </label>
        <label class="chat-attach-btn" :class="{ busy: voiceBusy }" :title="t('cottageChat.uploadAudioAria')" :aria-label="t('cottageChat.uploadAudioAria')">
          <input type="file" accept="audio/*" hidden @change="onPickAudioFile" />
          <FileAudio :size="19" :stroke-width="2" aria-hidden="true" />
        </label>
        <button
          type="button"
          class="chat-attach-btn"
          :class="{ busy: voiceBusy, recording: voiceRecording }"
          :disabled="voiceBusy || uploading"
          :aria-label="voiceRecording ? t('cottageChat.stopRecordingAria') : t('cottageChat.startRecordingAria')"
          :title="voiceRecording ? t('cottageChat.stopRecordingAria') : t('cottageChat.startRecordingAria')"
          @click="voiceRecording ? stopVoiceRecording() : startVoiceRecording()"
        >
          <Square v-if="voiceRecording" :size="17" :stroke-width="2" fill="currentColor" aria-hidden="true" />
          <Mic v-else :size="19" :stroke-width="2" aria-hidden="true" />
        </button>
        <textarea
          ref="inputEl"
          v-model="draft"
          class="chat-textarea"
          rows="1"
          maxlength="4000"
          :disabled="!!voiceDraft"
          :aria-label="t('cottageChat.messageContentAria')"
          :placeholder="voiceDraft ? t('cottageChat.voiceReadyPlaceholder') : t('cottageChat.whisperPlaceholder')"
          @keydown="onKeydown"
          @input="onDraftInput"
          @blur="stopTypingSoon"
        ></textarea>
        <button type="submit" class="chat-send" :disabled="sendDisabled">
          <SendHorizontal :size="17" :stroke-width="2" aria-hidden="true" />
          <span>{{ sendButtonText }}</span>
        </button>
      </div>
      <p v-if="voiceRecording" class="chat-recording-tip">{{ t('cottageChat.recordingTip', { time: formatSeconds(recordingElapsedSec) }) }}</p>
      </form>
    </section>

    <!-- E2E chat passphrase dialog -->
    <transition name="e2e-pop">
      <div v-if="showE2EDialog" class="e2e-overlay" @click.self="showE2EDialog = false">
        <div class="e2e-card">
          <h3 class="e2e-title">
            <LockKeyhole :size="20" :stroke-width="2" aria-hidden="true" />
            {{
              e2eDialogMode === "setup" ? t('cottageChat.e2eDialogTitleSetup') :
              e2eDialogMode === "unlock" ? t('cottageChat.e2eDialogTitleUnlock') :
              t('cottageChat.e2eDialogTitleRekey')
            }}
          </h3>
          <p class="e2e-hint">
            {{
              e2eDialogMode === "setup"
                ? t('cottageChat.e2eHintSetup')
                : e2eDialogMode === "unlock"
                ? t('cottageChat.e2eHintUnlock')
                : t('cottageChat.e2eHintRekey')
            }}
          </p>
          <input
            v-model="e2ePassphrase"
            type="password"
            class="e2e-input"
            :placeholder="t('cottageChat.passphrasePlaceholder')"
            autocomplete="new-password"
            @keyup.enter="submitE2EPassphrase"
          />
          <div class="e2e-actions">
            <button class="e2e-cancel" type="button" :disabled="e2eBusy" @click="showE2EDialog = false">{{ t('cottageChat.cancel') }}</button>
            <button class="e2e-confirm" type="button" :disabled="e2eBusy" @click="submitE2EPassphrase">
              {{ e2eBusy ? t('cottageChat.processing') : t('cottageChat.confirm') }}
            </button>
          </div>
          <button
            v-if="chatE2EEnabled"
            class="e2e-disable"
            type="button"
            @click="disableE2E"
          >{{ t('cottageChat.disableTemporarily') }}</button>
        </div>
      </div>
    </transition>

    <transition name="poke-pop">
      <div v-if="pokeFlash" class="poke-flash">
        <div class="poke-flash-emoji">{{ pokeFlash.emoji }}</div>
        <div class="poke-flash-text">{{ pokeFlash.text }}</div>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed, inject, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import {
  Archive,
  ArrowLeft,
  CalendarClock,
  ChartNoAxesColumnIncreasing,
  ChevronDown,
  FileAudio,
  ImagePlus,
  Images,
  LoaderCircle,
  LockKeyhole,
  LockKeyholeOpen,
  MessageCircleHeart,
  Mic,
  Pin,
  RefreshCw,
  Reply,
  Search,
  SendHorizontal,
  Square,
  Star,
  Undo2,
  X,
} from "@lucide/vue";
import {
  clearPinnedQuote,
  favoriteChatMessage,
  fetchChatKeywords,
  fetchChatMediaPanel,
  fetchChatMemoryCard,
  fetchChatMessages,
  fetchChatState,
  fetchFutureChatMessages,
  fetchMe,
  fetchPinnedQuote,
  markChatRead,
  recallChatMessage,
  resolveAssetUrl,
  searchChatMessages,
  sendChatMessage,
  sendPoke,
  setPinnedQuote,
  unfavoriteChatMessage,
  uploadChatAudio,
  uploadChatEncryptedMedia,
  uploadChatImage,
} from "../../../lib/api";
import { createCottageSocket } from "../../../lib/cottageChatWs";
import {
  decryptChatBytes,
  decryptChatText,
  encryptChatRaw,
  encryptChatText,
  isChatUnlocked,
  unlockChatKey,
  createChatKeySetup,
  hasStoredChatSession,
  clearChatSession,
} from "../../../lib/chatCrypto";
import {
  fetchChatKeyMeta,
  rekeyChatKey,
  setupChatKey,
} from "../../../lib/api";
import { parseError } from "../../../utils/helpers";

const showMessage = inject("showMessage", () => {});
const { t } = useI18n();
const CHAT_DRAFT_STORAGE_KEY = "love_cottage_chat_draft_v1";
const RECALL_WINDOW_MS = 2 * 60 * 1000;
const TYPING_IDLE_MS = 1800;

const pokes = computed(() => [
  { kind: "miss", emoji: "💗", label: t('cottageChat.pokeMissLabel') },
  { kind: "hug", emoji: "🤗", label: t('cottageChat.pokeHugLabel') },
  { kind: "poke", emoji: "👉", label: t('cottageChat.pokePokeLabel') },
]);
const POKE_EMOJI = { miss: "💗", hug: "🤗", poke: "👉", kiss: "😘" };

const messages = ref([]);
const loading = ref(true);
const loadingOlder = ref(false);
const hasMore = ref(false);
const nextBeforeId = ref(null);
const firstUnreadMid = ref("");
const partner = ref({ uid: "", nickname: "", online: false, onlineSince: null, lastActiveAt: null });
const partnerTyping = ref({ isTyping: false, at: null });
const myUid = ref("");
const draft = ref("");
const futureAtInput = ref("");
const replyingTo = ref(null);
const sending = ref(false);
const uploading = ref(false);
const voiceBusy = ref(false);
const voiceRecording = ref(false);
const recordingElapsedSec = ref(0);
const voiceDraft = ref(null);
const pokeBusy = ref(false);
const pokeFlash = ref(null);
const panelLoading = ref(false);
const actionBusyMid = ref("");
const decryptedMediaUrls = ref({});
// Concurrency limiter: at most 3 simultaneous media fetch+decrypt operations.
const MAX_CONCURRENT_MEDIA_DECRYPT = 3;
const MAX_DECRYPTED_URL_CACHE = 50;
const MEDIA_FETCH_TIMEOUT_MS = 30_000;
let activeMediaDecrypts = 0;
const pendingMediaQueue = [];
const pinBusy = ref(false);
const pinnedQuote = ref(null);
const futureMessages = ref([]);
const keywordItems = ref([]);
const memoryCard = ref(null);
const mediaPanel = ref({ images: [], stickers: [], voices: [], favorites: [] });
const nowTick = ref(Date.now());
const toolsOpen = ref(false);
const activeTool = ref("pinned");

// ── Search state ───────────────────────────────────────────────────
const searchQuery = ref("");
const searchResults = ref([]);
const searchBusy = ref(false);
const searchSearched = ref(false);
let searchDebounceTimer = null;

// ── E2E chat state ────────────────────────────────────────────────
// When ``chatE2EEnabled`` is true, outgoing text messages are encrypted
// client-side before the POST and incoming encrypted messages are
// decrypted on receipt. The key is held in a module-level singleton
// (chatCrypto.js) and never sent to the server.
const chatE2EEnabled = ref(false);
const chatE2EUnlocked = ref(false);
const showE2EDialog = ref(false);
const e2ePassphrase = ref("");
const e2eBusy = ref(false);
const e2eDialogMode = ref("setup"); // "setup" | "unlock" | "rekey"

const listEl = ref(null);
const inputEl = ref(null);
let socket = null;
let pokeFlashTimer = null;
let panelsRefreshTimer = null;
let typingStopTimer = null;
let partnerTypingTimer = null;
let typingSent = false;
let nowTimer = null;
let mediaRecorder = null;
let mediaChunks = [];
let mediaStream = null;
let recordTimer = null;
let recordStartedAt = 0;
let componentAlive = true;
let voiceRequestId = 0;
let lifecycleGeneration = 0;
let messagesRequestGeneration = 0;

const sendDisabled = computed(() => {
  if (sending.value || uploading.value || voiceBusy.value) return true;
  return !draft.value.trim() && !voiceDraft.value;
});

const sendButtonText = computed(() => {
  if (sending.value || uploading.value || voiceBusy.value) return "…";
  if (voiceDraft.value) return futureAtInput.value ? t('cottageChat.sendVoiceFuture') : t('cottageChat.sendVoiceButton');
  return futureAtInput.value ? t('cottageChat.sendFuture') : t('cottageChat.sendButton');
});

const toolsSummary = computed(() => {
  const parts = [];
  parts.push(pinnedQuote.value ? t('cottageChat.pinnedSummary') : t('cottageChat.noPinnedSummary'));
  if (futureMessages.value.length) parts.push(t('cottageChat.futureSummary', { n: futureMessages.value.length }));
  if (mediaPanel.value.favorites.length) parts.push(t('cottageChat.favoriteSummary', { n: mediaPanel.value.favorites.length }));
  return parts.join(t('cottageChat.summaryJoin'));
});

const partnerStatusText = computed(() => {
  if (partnerTyping.value.isTyping) {
    return t('cottageChat.typingStatus', { name: partner.value.nickname || t('cottageChat.them') });
  }
  if (partner.value.online) {
    if (partner.value.onlineSince) return t('cottageChat.onlineStatusTime', { time: formatRelativeTime(partner.value.onlineSince) });
    return t('cottageChat.onlineStatus');
  }
  if (partner.value.lastActiveAt) {
    return t('cottageChat.lastActiveStatus', { time: formatDayTime(partner.value.lastActiveAt) });
  }
  return t('cottageChat.offlineStatus');
});

function initialOf(name) {
  const s = String(name || "").trim();
  return s ? s.slice(0, 1).toUpperCase() : t('cottageChat.them');
}

function compareMessages(a, b) {
  const aId = Number(a?.id || 0);
  const bId = Number(b?.id || 0);
  if (aId && bId && aId !== bId) return aId - bId;
  const aAt = new Date(a?.created_at || 0).getTime();
  const bAt = new Date(b?.created_at || 0).getTime();
  return aAt - bAt;
}

function normalizeReply(reply) {
  if (!reply || !reply.mid) return null;
  return {
    mid: reply.mid,
    sender_nickname: reply.sender_nickname || "",
    type: reply.type || "text",
    content: reply.content ?? null,
    is_recalled: !!reply.is_recalled
  };
}

function normalizeMessage(payload) {
  if (!payload || !payload.mid) return null;
  return {
    id: Number(payload.id || 0),
    mid: payload.mid,
    sender_uid: payload.sender_uid || "",
    sender_nickname: payload.sender_nickname || "",
    is_self: payload.is_self != null ? !!payload.is_self : payload.sender_uid === myUid.value,
    type: payload.type || "text",
    content: payload.content ?? null,
    media_url: payload.media_url ?? null,
    audio_duration_sec: payload.audio_duration_sec ?? null,
    is_favorite: !!payload.is_favorite,
    is_future: !!payload.is_future,
    is_recalled: payload.is_recalled != null ? !!payload.is_recalled : !!payload.recalled_at,
    can_recall: payload.can_recall != null ? !!payload.can_recall : null,
    recalled_at: payload.recalled_at || null,
    reply_to: normalizeReply(payload.reply_to),
    read_at: payload.read_at || null,
    visible_at: payload.visible_at || null,
    created_at: payload.created_at || payload.visible_at || new Date().toISOString(),
    is_encrypted: payload.is_encrypted === true,
    iv: payload.iv || null,
    ciphertext: payload.ciphertext || null,
    algo: payload.algo || null,
    // Marked true after a successful client-side decrypt attempt.
    _decryption_failed: false,
  };
}

function normalizeMessages(items) {
  return (items || []).map(normalizeMessage).filter(Boolean).sort(compareMessages);
}

/**
 * Best-effort client-side decrypt for incoming messages that the sender
 * wrapped in E2E. The fallback is a clear encrypted-message placeholder.
 * placeholder so the chat never silently shows raw ciphertext.
 */
async function decryptIncoming(item) {
  if (!item || !item.is_encrypted) return item;
  if (item.type === "text") {
    if (!isChatUnlocked()) {
      return { ...item, content: null, _decryption_failed: true };
    }
    try {
      const plain = await decryptChatText(item.iv, item.ciphertext);
      if (plain == null) {
        return { ...item, content: null, _decryption_failed: true };
      }
      return { ...item, content: plain, _decryption_failed: false };
    } catch (_) {
      return { ...item, content: null, _decryption_failed: true };
    }
  }
  // Encrypted media (image / sticker / voice): kick off async decryption.
  // The message renders a placeholder until the blob URL is ready.
  if (["image", "sticker", "voice"].includes(item.type)) {
    if (!isChatUnlocked()) {
      return { ...item, _decryption_failed: true };
    }
    if (!decryptedMediaUrls.value[item.mid]) {
      enqueueMediaDecrypt(item);
    }
    return item;
  }
  return item;
}

/**
 * Fetch the encrypted media file, decrypt it, and cache a blob URL for
 * display. Uses a concurrency limiter (max 3), fetch timeout, component
 * lifetime check, MIME detection from magic bytes, and LRU eviction.
 */
function enqueueMediaDecrypt(item) {
  if (activeMediaDecrypts < MAX_CONCURRENT_MEDIA_DECRYPT) {
    runMediaDecrypt(item);
  } else {
    pendingMediaQueue.push(item);
  }
}

async function runMediaDecrypt(item) {
  activeMediaDecrypts += 1;
  try {
    if (!componentAlive) return;
    const url = resolveAssetUrl(item.media_url);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), MEDIA_FETCH_TIMEOUT_MS);
    try {
      const response = await fetch(url, { signal: controller.signal });
      if (!response.ok) return;
      const encryptedBuffer = await response.arrayBuffer();
      if (!componentAlive) return;
      const decryptedBuffer = await decryptChatBytes(item.iv, encryptedBuffer);
      if (!componentAlive) return;
      const mimeType = detectMimeType(decryptedBuffer);
      const blob = new Blob([decryptedBuffer], { type: mimeType });
      cacheMediaUrl(item.mid, URL.createObjectURL(blob));
    } finally {
      clearTimeout(timeout);
    }
  } catch (_) {
    // Leave placeholder; user can re-enter the chat to retry.
  } finally {
    activeMediaDecrypts -= 1;
    if (pendingMediaQueue.length > 0 && componentAlive) {
      runMediaDecrypt(pendingMediaQueue.shift());
    }
  }
}

/**
 * Detect MIME type from the first few bytes of a decrypted file.
 * Avoids hardcoding image/png or audio/webm which may not match.
 */
function detectMimeType(buffer) {
  const b = new Uint8Array(buffer, 0, Math.min(12, buffer.byteLength));
  if (b[0] === 0xff && b[1] === 0xd8) return "image/jpeg";
  if (b[0] === 0x89 && b[1] === 0x50 && b[2] === 0x4e && b[3] === 0x47) return "image/png";
  if (b[0] === 0x47 && b[1] === 0x49 && b[2] === 0x46) return "image/gif";
  if (b[0] === 0x52 && b[1] === 0x49 && b[2] === 0x46 && b[3] === 0x46) return "image/webp";
  if (b[0] === 0x1a && b[1] === 0x45 && b[2] === 0xdf && b[3] === 0xa3) return "audio/webm";
  if (b[0] === 0x4f && b[1] === 0x67 && b[2] === 0x67 && b[3] === 0x53) return "audio/ogg";
  if (b[0] === 0x49 && b[1] === 0x44 && b[2] === 0x33) return "audio/mpeg";
  return "application/octet-stream";
}

/**
 * Store a decrypted blob URL with LRU eviction. When the cache exceeds
 * MAX_DECRYPTED_URL_CACHE entries, the oldest entries are revoked.
 */
function cacheMediaUrl(mid, url) {
  const entries = Object.entries(decryptedMediaUrls.value);
  if (entries.length >= MAX_DECRYPTED_URL_CACHE) {
    const evictCount = entries.length - MAX_DECRYPTED_URL_CACHE + 1;
    for (const [, oldUrl] of entries.slice(0, evictCount)) {
      URL.revokeObjectURL(oldUrl);
    }
    decryptedMediaUrls.value = {
      ...Object.fromEntries(entries.slice(evictCount)),
      [mid]: url,
    };
  } else {
    decryptedMediaUrls.value = { ...decryptedMediaUrls.value, [mid]: url };
  }
}

/**
 * Resolve the display URL for a media message. For encrypted media, use
 * the decrypted blob URL; for plaintext, use the server URL directly.
 */
function mediaSrc(m) {
  if (m.is_encrypted) {
    return decryptedMediaUrls.value[m.mid] || null;
  }
  return resolveAssetUrl(m.media_url);
}

async function decryptAll(items) {
  return Promise.all((items || []).map((item) => decryptIncoming(item)));
}

/**
 * Re-decrypt all encrypted messages currently in the list. Called after
 * the user unlocks (or sets up) the E2E key so messages that were loaded
 * while the chat was still locked become readable without a page reload.
 */
async function redecryptMessages() {
  const encrypted = messages.value.filter((m) => m.is_encrypted);
  if (!encrypted.length) return;
  const decrypted = await Promise.all(encrypted.map((m) => decryptIncoming(m)));
  mergeMessages(decrypted);
}

function isNearBottom() {
  const el = listEl.value;
  if (!el) return true;
  return el.scrollHeight - el.scrollTop - el.clientHeight < 120;
}

async function scrollToBottom(force = false) {
  await nextTick();
  const el = listEl.value;
  if (el && (force || isNearBottom())) {
    el.scrollTop = el.scrollHeight;
  }
}

async function scrollToMessage(mid, block = "center") {
  if (!mid) return false;
  await nextTick();
  const el = listEl.value;
  if (!el) return false;
  const node = el.querySelector(`[data-mid="${mid}"]`);
  if (!node) return false;
  node.scrollIntoView({ block, behavior: "smooth" });
  return true;
}

async function openMessageFromTools(mid) {
  toolsOpen.value = false;
  await nextTick();
  await scrollToMessage(mid);
}

function runSearch() {
  const q = searchQuery.value.trim();
  if (!q) {
    searchResults.value = [];
    searchSearched.value = false;
    return;
  }
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
  searchDebounceTimer = setTimeout(async () => {
    searchBusy.value = true;
    searchSearched.value = true;
    try {
      const data = await searchChatMessages({ q, limit: 30 });
      const serverItems = (data.items || []).map((m) => ({ ...m, _source: "server" }));
      // Also search locally loaded encrypted messages (server can't decrypt them).
      const localEncrypted = messages.value.filter(
        (m) =>
          m.is_encrypted &&
          !m.is_recalled &&
          m.content &&
          typeof m.content === "string" &&
          m.content.toLowerCase().includes(q.toLowerCase()),
      ).map((m) => ({ ...m, _source: "local" }));
      // Merge, dedup by mid (server results take priority).
      const seen = new Set(serverItems.map((m) => m.mid));
      const merged = [...serverItems, ...localEncrypted.filter((m) => !seen.has(m.mid))];
      searchResults.value = merged;
    } catch {
      searchResults.value = [];
    } finally {
      searchBusy.value = false;
    }
  }, 350);
}

function onSearchInput() {
  runSearch();
}

async function openSearchResult(mid) {
  toolsOpen.value = false;
  await nextTick();
  const found = await scrollToMessage(mid);
  if (!found) {
    showMessage(t('cottageChat.notInRange'));
  }
}

async function scrollToFirstUnread() {
  if (!firstUnreadMid.value) {
    await scrollToBottom(true);
    return;
  }
  const found = await scrollToMessage(firstUnreadMid.value, "center");
  if (!found) {
    await scrollToBottom(true);
  }
}

function mergeMessages(items) {
  const newItems = normalizeMessages(items);
  if (newItems.length === 0) return;
  const arr = messages.value;
  // Merge two sorted arrays (both sorted by compareMessages) in O(n+m).
  const result = [];
  let i = 0, j = 0;
  while (i < arr.length && j < newItems.length) {
    const cmp = compareMessages(arr[i], newItems[j]);
    if (cmp < 0) {
      result.push(arr[i++]);
    } else if (cmp > 0) {
      result.push(newItems[j++]);
    } else {
      const merged = { ...arr[i], ...newItems[j] };
      // Mirror the upsertMessage guard: a decrypted plaintext (or a
      // locally-restored one) must never be overwritten by an undecrypted
      // server copy whose content is null, otherwise an already-readable
      // message snaps back to the [encrypted] placeholder.
      if (merged.content == null && arr[i].content != null) {
        merged.content = arr[i].content;
        merged._decryption_failed = arr[i]._decryption_failed;
      }
      if (merged.can_recall == null && arr[i].can_recall === true) {
        merged.can_recall = arr[i].can_recall;
      }
      result.push(merged);
      i++; j++;
    }
  }
  while (i < arr.length) result.push(arr[i++]);
  while (j < newItems.length) result.push(newItems[j++]);
  messages.value = result;
}

function upsertMessage(msg, { toBottom = false } = {}) {
  const normalized = normalizeMessage(msg);
  if (!normalized) return;
  const wasNearBottom = isNearBottom();
  const arr = messages.value;
  const normId = Number(normalized.id || 0);

  // Binary search by id (messages are sorted by id via compareMessages).
  let lo = 0, hi = arr.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (Number(arr[mid].id || 0) < normId) lo = mid + 1;
    else hi = mid;
  }

  if (lo < arr.length && arr[lo].mid === normalized.mid) {
    // Update existing message in place - no sort needed.
    const existing = arr[lo];
    const next = { ...existing, ...normalized };
    // Don't let a WS echo with null content wipe out a locally-known
    // plaintext (e.g. our own just-sent encrypted message).
    if (next.content == null && existing.content != null) {
      next.content = existing.content;
      next._decryption_failed = existing._decryption_failed;
    }
    // WS broadcast (event_payload) omits can_recall since it's per-user;
    // preserve the server-provided value instead of overwriting with null.
    if (next.can_recall == null && existing.can_recall === true) {
      next.can_recall = existing.can_recall;
    }
    messages.value = [...arr.slice(0, lo), next, ...arr.slice(lo + 1)];
  } else {
    // Insert new message at binary-searched position - no sort needed.
    messages.value = [...arr.slice(0, lo), normalized, ...arr.slice(lo)];
  }

  if (toBottom || wasNearBottom) {
    scrollToBottom(toBottom);
  }
}

function sameDay(a, b) {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

const dayDividerIndices = computed(() => {
  const set = new Set();
  const arr = messages.value;
  if (arr.length === 0) return set;
  set.add(0);
  for (let i = 1; i < arr.length; i++) {
    const cur = new Date(arr[i].created_at);
    const prev = new Date(arr[i - 1].created_at);
    if (Number.isNaN(cur.getTime()) || Number.isNaN(prev.getTime())) continue;
    if (!sameDay(cur, prev)) set.add(i);
  }
  return set;
});

function showUnreadDivider(message) {
  return !!message?.mid && message.mid === firstUnreadMid.value;
}

function formatDay(raw) {
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return "";
  const now = new Date();
  if (sameDay(d, now)) return t('cottageChat.today');
  const yest = new Date(now);
  yest.setDate(now.getDate() - 1);
  if (sameDay(d, yest)) return t('cottageChat.yesterday');
  return d.toLocaleDateString("zh-CN", { month: "long", day: "numeric" });
}

function formatTime(raw) {
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function formatDayTime(raw) {
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("zh-CN", {
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatSeconds(totalSec) {
  const s = Math.max(0, Math.round(totalSec || 0));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${m}:${String(r).padStart(2, "0")}`;
}

function formatRelativeTime(raw) {
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return t('cottageChat.justNow');
  const diffSec = Math.max(0, Math.round((nowTick.value - d.getTime()) / 1000));
  if (diffSec < 60) return t('cottageChat.justNow');
  if (diffSec < 3600) return t('cottageChat.minutesRelative', { n: Math.floor(diffSec / 60) });
  if (diffSec < 86400) return t('cottageChat.hoursRelative', { n: Math.floor(diffSec / 3600) });
  return t('cottageChat.daysRelative', { n: Math.floor(diffSec / 86400) });
}

function formatLocalInputValue(value) {
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return t('cottageChat.later');
  return formatDayTime(d.toISOString());
}

function replySnippet(reply) {
  if (!reply) return "";
  if (reply.is_recalled) return t('cottageChat.recalledReply');
  if (reply.type === "voice") return t('cottageChat.voiceSnippet');
  if (reply.type === "image") return t('cottageChat.imageSnippet');
  if (reply.type === "sticker") return t('cottageChat.stickerSnippet');
  return reply.content || t('cottageChat.messageSnippet');
}

function recalledLabel(message) {
  return message?.is_self ? t('cottageChat.recalledSelf') : t('cottageChat.recalledPartner');
}

function messageSnippet(message) {
  if (!message) return "";
  if (message.is_recalled) return recalledLabel(message);
  if (message.type === "voice") return t('cottageChat.voiceWithDuration', { time: formatSeconds(message.audio_duration_sec) });
  if (message.type === "image") return t('cottageChat.imageSnippet');
  if (message.type === "sticker") return t('cottageChat.stickerSnippet');
  return message.content || t('cottageChat.messageSnippet');
}

function isMediaBubble(message) {
  return !!message && !message.is_recalled && (message.type === "image" || message.type === "sticker");
}

function canRecallMessage(message) {
  if (!message || !message.is_self || message.is_recalled || message.is_future) return false;
  if (message.can_recall === true) return true;
  const createdAt = new Date(message.created_at);
  if (Number.isNaN(createdAt.getTime())) return false;
  return nowTick.value - createdAt.getTime() <= RECALL_WINDOW_MS;
}

function getVisibleAtPayload() {
  if (!futureAtInput.value) return undefined;
  const date = new Date(futureAtInput.value);
  if (Number.isNaN(date.getTime())) {
    showMessage(t("cottageChat.futureTimeInvalid"));
    return null;
  }
  return date.toISOString();
}

function clearFutureSchedule() {
  futureAtInput.value = "";
}

function clearReply() {
  replyingTo.value = null;
}

function replyToMessage(message) {
  replyingTo.value = message;
  nextTick(() => inputEl.value?.focus());
}

function saveDraftToStorage() {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      CHAT_DRAFT_STORAGE_KEY,
      JSON.stringify({
        draft: draft.value,
        futureAtInput: futureAtInput.value
      })
    );
  } catch (_) {
    /* ignore */
  }
}

function restoreDraftFromStorage() {
  if (typeof window === "undefined") return;
  try {
    const raw = window.localStorage.getItem(CHAT_DRAFT_STORAGE_KEY);
    if (!raw) return;
    const data = JSON.parse(raw);
    draft.value = String(data?.draft || "");
    futureAtInput.value = String(data?.futureAtInput || "");
  } catch (_) {
    /* ignore */
  }
}

function autoGrow() {
  const el = inputEl.value;
  if (!el) return;
  el.style.height = "auto";
  const nextHeight = Math.min(el.scrollHeight, 140);
  el.style.height = `${nextHeight}px`;
  el.style.overflowY = el.scrollHeight > 140 ? "auto" : "hidden";
}

function onDraftInput() {
  autoGrow();
  if (!draft.value.trim()) {
    stopTypingSoon();
    return;
  }
  sendTyping(true);
}

let imageLoadScrollTimer = null;
function onImageLoad() {
  if (imageLoadScrollTimer) clearTimeout(imageLoadScrollTimer);
  imageLoadScrollTimer = setTimeout(() => scrollToBottom(), 100);
}

function previewImage(url) {
  if (!url) return;
  const resolved = url.startsWith("blob:") ? url : resolveAssetUrl(url);
  if (!resolved) return;
  const opened = window.open(resolved, "_blank", "noopener,noreferrer");
  if (opened) opened.opener = null;
}

function clearVoiceDraft() {
  if (voiceDraft.value?.previewUrl) {
    URL.revokeObjectURL(voiceDraft.value.previewUrl);
  }
  voiceDraft.value = null;
}

function stopTypingSoon() {
  if (typingStopTimer) clearTimeout(typingStopTimer);
  typingStopTimer = setTimeout(() => sendTyping(false), 100);
}

function scheduleTypingStop() {
  if (typingStopTimer) clearTimeout(typingStopTimer);
  typingStopTimer = setTimeout(() => sendTyping(false), TYPING_IDLE_MS);
}

function sendTyping(isTyping) {
  if (!socket) return;
  if (isTyping) {
    socket.send({ type: "TYPING", payload: { is_typing: true } });
    typingSent = true;
    scheduleTypingStop();
    return;
  }
  if (!typingSent) return;
  socket.send({ type: "TYPING", payload: { is_typing: false } });
  typingSent = false;
}

function queuePanelsRefresh() {
  if (panelsRefreshTimer) clearTimeout(panelsRefreshTimer);
  panelsRefreshTimer = setTimeout(() => {
    panelsRefreshTimer = null;
    loadPanels({ silent: true });
  }, 300);
}

function applyPartnerState(state) {
  partner.value = {
    uid: state?.partner_uid || partner.value.uid || "",
    nickname: state?.partner_nickname || partner.value.nickname || "",
    online: !!state?.partner_online,
    onlineSince: state?.partner_online_since || null,
    lastActiveAt: state?.partner_last_active_at || null,
  };
}

async function loadPanels({ silent = false } = {}) {
  const lifecycle = lifecycleGeneration;
  if (!silent) panelLoading.value = true;
  const results = await Promise.allSettled([
    fetchPinnedQuote(),
    fetchFutureChatMessages(),
    fetchChatKeywords(),
    fetchChatMemoryCard(),
    fetchChatMediaPanel({ limit: 6 }),
  ]);
  if (!componentAlive || lifecycle !== lifecycleGeneration) return;
  if (results[0].status === "fulfilled") pinnedQuote.value = normalizeMessage(results[0].value.message);
  if (results[1].status === "fulfilled") futureMessages.value = normalizeMessages(results[1].value.items);
  if (results[2].status === "fulfilled") keywordItems.value = results[2].value.items || [];
  if (results[3].status === "fulfilled") memoryCard.value = results[3].value || null;
  if (results[4].status === "fulfilled") {
    mediaPanel.value = {
      images: normalizeMessages(results[4].value.images),
      stickers: normalizeMessages(results[4].value.stickers),
      voices: normalizeMessages(results[4].value.voices),
      favorites: normalizeMessages(results[4].value.favorites),
    };
  }
  if (!silent) {
    const rejected = results.find((item) => item.status === "rejected");
    if (rejected) {
      showMessage(parseError(rejected.reason));
    }
    panelLoading.value = false;
  }
}

async function loadInitial() {
  const lifecycle = lifecycleGeneration;
  const requestGeneration = ++messagesRequestGeneration;
  loading.value = true;
  try {
    const data = await fetchChatMessages({ limit: 30 });
    if (
      !componentAlive ||
      lifecycle !== lifecycleGeneration ||
      requestGeneration !== messagesRequestGeneration
    ) return;
    // Best-effort decrypt the freshly-loaded page. We don't await
    // (the messages can render their [encrypted] placeholder first
    // and upgrade as keys become available).
    const decrypted = await decryptAll(data.items);
    if (
      !componentAlive ||
      lifecycle !== lifecycleGeneration ||
      requestGeneration !== messagesRequestGeneration
    ) return;
    mergeMessages(decrypted);
    hasMore.value = !!data.has_more;
    nextBeforeId.value = data.next_before_id;
    firstUnreadMid.value = data.first_unread_mid || "";
    await scrollToFirstUnread();
  } catch (error) {
    if (
      componentAlive &&
      lifecycle === lifecycleGeneration &&
      requestGeneration === messagesRequestGeneration
    ) {
      showMessage(parseError(error));
    }
  } finally {
    if (
      componentAlive &&
      lifecycle === lifecycleGeneration &&
      requestGeneration === messagesRequestGeneration
    ) {
      loading.value = false;
    }
  }
}

async function loadOlder() {
  if (loadingOlder.value || !hasMore.value || nextBeforeId.value == null) return;
  loadingOlder.value = true;
  const el = listEl.value;
  const prevHeight = el ? el.scrollHeight : 0;
  try {
    const data = await fetchChatMessages({ limit: 30, before_id: nextBeforeId.value });
    // Decrypt before merging: these are E2E messages from older pages, and
    // merging raw ciphertext copies would both show [encrypted] placeholders
    // and overwrite already-decrypted duplicates via the merge guard.
    const decrypted = await decryptAll(data.items);
    mergeMessages(decrypted);
    hasMore.value = !!data.has_more;
    nextBeforeId.value = data.next_before_id;
    if (!firstUnreadMid.value && data.first_unread_mid) {
      firstUnreadMid.value = data.first_unread_mid;
    }
    await nextTick();
    if (el) {
      el.scrollTop = el.scrollHeight - prevHeight;
    }
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    loadingOlder.value = false;
  }
}

function onScroll() {
  const el = listEl.value;
  if (el && el.scrollTop < 60 && hasMore.value && !loadingOlder.value) {
    loadOlder();
  }
}

async function markReadSafe() {
  try {
    await markChatRead();
  } catch (_) {
    /* ignore */
  }
}

async function sendTextMessage(text, visibleAt) {
  // When E2E is on AND the chat key is unlocked, encrypt client-side
  // before POST. The server only ever sees opaque ciphertext + IV; the
  // partner's browser decrypts on receipt.
  let payload = {
    type: "text",
    content: text,
    visible_at: visibleAt,
    reply_to_mid: replyingTo.value?.mid || undefined,
  };
  if (chatE2EEnabled.value && isChatUnlocked()) {
    try {
      const envelope = await encryptChatText(text);
      payload = {
        ...payload,
        is_encrypted: true,
        iv: envelope.iv,
        ciphertext: envelope.ciphertext,
        algo: "AES-GCM",
        // Server is told the message body itself is just the placeholder;
        // the real content is the ciphertext blob above.
        content: null,
      };
    } catch {
      showMessage("加密失败，消息未发送");
      return;
    }
  } else if (chatE2EEnabled.value) {
    showMessage(t("cottageChat.chatLocked"));
    return;
  }
  const msg = await sendChatMessage(payload);
  // For E2E messages the server returns content=null (only ciphertext is
  // stored). Restore the plaintext we already hold so our own message
  // displays immediately without waiting for a WS decrypt round-trip.
  if (msg.is_encrypted && msg.content == null && text) {
    msg.content = text;
  }
  draft.value = "";
  autoGrow();
  clearReply();
  clearFutureSchedule();
  sendTyping(false);
  if (msg.is_future) {
    showMessage(t('cottageChat.futureSent', { time: formatDayTime(msg.visible_at) }));
    await loadPanels();
    return;
  }
  upsertMessage(msg, { toBottom: true });
  queuePanelsRefresh();
}

async function sendVoiceMessage(visibleAt) {
  if (!voiceDraft.value) return;
  let upload;
  let encryptionEnvelope = null;
  if (chatE2EEnabled.value && isChatUnlocked()) {
    const arrayBuffer = await voiceDraft.value.file.arrayBuffer();
    const { iv, cipherBuffer } = await encryptChatRaw(arrayBuffer);
    const encryptedBlob = new Blob([cipherBuffer], { type: "application/octet-stream" });
    upload = await uploadChatEncryptedMedia(encryptedBlob, "voice.enc");
    encryptionEnvelope = { is_encrypted: true, iv, algo: "AES-GCM" };
  } else if (chatE2EEnabled.value) {
    showMessage(t('cottageChat.chatLocked'));
    return;
  } else {
    upload = await uploadChatAudio(voiceDraft.value.file);
  }
  const msg = await sendChatMessage({
    type: "voice",
    media_url: upload.url,
    audio_duration_sec: Math.max(1, Math.round(voiceDraft.value.durationSec || 1)),
    visible_at: visibleAt,
    reply_to_mid: replyingTo.value?.mid || undefined,
    ...encryptionEnvelope,
  });
  // For E2E voice: create a local blob URL from the original file so the
  // sender hears it immediately without a decrypt round-trip.
  if (msg.is_encrypted && voiceDraft.value.file) {
    decryptedMediaUrls.value[msg.mid] = URL.createObjectURL(voiceDraft.value.file);
  }
  clearVoiceDraft();
  clearReply();
  clearFutureSchedule();
  if (msg.is_future) {
    showMessage(t("cottageChat.voiceFutureSent", { time: formatDayTime(msg.visible_at) }));
    await loadPanels();
    return;
  }
  upsertMessage(msg, { toBottom: true });
  queuePanelsRefresh();
}

async function send() {
  const text = draft.value.trim();
  if (sendDisabled.value) return;
  const visibleAt = getVisibleAtPayload();
  if (visibleAt === null) return;
  sending.value = true;
  try {
    if (voiceDraft.value) {
      await sendVoiceMessage(visibleAt);
    } else {
      await sendTextMessage(text, visibleAt);
    }
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    sending.value = false;
  }
}

async function onPickImage(evt) {
  const file = evt.target.files && evt.target.files[0];
  evt.target.value = "";
  if (!file || uploading.value) return;
  const visibleAt = getVisibleAtPayload();
  if (visibleAt === null) return;
  uploading.value = true;
  try {
    let upload;
    let encryptionEnvelope = null;
    if (chatE2EEnabled.value && isChatUnlocked()) {
      const arrayBuffer = await file.arrayBuffer();
      const { iv, cipherBuffer } = await encryptChatRaw(arrayBuffer);
      const encryptedBlob = new Blob([cipherBuffer], { type: "application/octet-stream" });
      upload = await uploadChatEncryptedMedia(encryptedBlob, "image.enc");
      encryptionEnvelope = { is_encrypted: true, iv, algo: "AES-GCM" };
    } else if (chatE2EEnabled.value) {
      showMessage(t('cottageChat.chatLocked'));
      return;
    } else {
      upload = await uploadChatImage(file);
    }
    if (upload && upload.url) {
      const msg = await sendChatMessage({
        type: "image",
        media_url: upload.url,
        visible_at: visibleAt,
        reply_to_mid: replyingTo.value?.mid || undefined,
        ...encryptionEnvelope,
      });
      // For E2E image: create a local blob URL from the original file so the
      // sender sees it immediately without a decrypt round-trip.
      if (msg.is_encrypted) {
        decryptedMediaUrls.value[msg.mid] = URL.createObjectURL(file);
      }
      clearReply();
      clearFutureSchedule();
      if (msg.is_future) {
        showMessage(t('cottageChat.imageFutureSent', { time: formatDayTime(msg.visible_at) }));
        await loadPanels();
        return;
      }
      upsertMessage(msg, { toBottom: true });
      queuePanelsRefresh();
    }
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    uploading.value = false;
  }
}

function loadMediaDuration(url, tagName = "audio") {
  return new Promise((resolve) => {
    const probe = document.createElement(tagName);
    probe.preload = "metadata";
    probe.onloadedmetadata = () => resolve(Number.isFinite(probe.duration) ? probe.duration : 0);
    probe.onerror = () => resolve(0);
    probe.src = url;
  });
}

async function setVoiceDraftFromFile(file, source) {
  clearVoiceDraft();
  const previewUrl = URL.createObjectURL(file);
  const durationSec = await loadMediaDuration(previewUrl, "audio");
  voiceDraft.value = {
    file,
    source,
    previewUrl,
    durationSec: Math.max(1, Math.round(durationSec || 1)),
  };
  draft.value = "";
  autoGrow();
}

async function onPickAudioFile(evt) {
  const file = evt.target.files && evt.target.files[0];
  evt.target.value = "";
  if (!file || voiceBusy.value || voiceRecording.value) return;
  voiceBusy.value = true;
  try {
    await setVoiceDraftFromFile(file, "file");
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    voiceBusy.value = false;
  }
}

function pickAudioMime() {
  const candidates = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"];
  if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) return "";
  return candidates.find((item) => MediaRecorder.isTypeSupported(item)) || "";
}

function stopVoiceStream(target = mediaStream) {
  if (target) {
    target.getTracks().forEach((track) => track.stop());
    if (mediaStream === target) mediaStream = null;
  }
}

async function startVoiceRecording() {
  if (voiceRecording.value || voiceBusy.value) return;
  if (typeof MediaRecorder === "undefined") {
    showMessage(t('cottageChat.recordingUnsupported'));
    return;
  }
  voiceBusy.value = true;
  const requestId = ++voiceRequestId;
  let acquiredStream = null;
  try {
    acquiredStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    if (!componentAlive || requestId !== voiceRequestId) {
      stopVoiceStream(acquiredStream);
      return;
    }
    mediaStream = acquiredStream;
    const mimeType = pickAudioMime();
    const recorder = mimeType
      ? new MediaRecorder(mediaStream, { mimeType })
      : new MediaRecorder(mediaStream);
    mediaRecorder = recorder;
    mediaChunks = [];
    recorder.ondataavailable = (event) => {
      if (!componentAlive || requestId !== voiceRequestId) return;
      if (event.data && event.data.size > 0) {
        mediaChunks.push(event.data);
      }
    };
    recorder.onstop = async () => {
      if (!componentAlive || requestId !== voiceRequestId) {
        stopVoiceStream(acquiredStream);
        return;
      }
      const contentType = recorder.mimeType || mimeType || "audio/webm";
      const ext = (contentType.split("/")[1] || "webm").split(";")[0];
      const blob = new Blob(mediaChunks, { type: contentType });
      const file = new File([blob], `chat-voice-${Date.now()}.${ext}`, { type: contentType });
      await setVoiceDraftFromFile(file, "record");
      stopVoiceStream(acquiredStream);
    };
    recorder.start();
    voiceRecording.value = true;
    recordingElapsedSec.value = 0;
    recordStartedAt = Date.now();
    if (recordTimer) clearInterval(recordTimer);
    recordTimer = setInterval(() => {
      recordingElapsedSec.value = Math.max(0, Math.round((Date.now() - recordStartedAt) / 1000));
    }, 250);
  } catch (error) {
    stopVoiceStream(acquiredStream);
    if (componentAlive && requestId === voiceRequestId) {
      showMessage(error?.message || t('cottageChat.micAccessFailed'));
    }
  } finally {
    if (componentAlive && requestId === voiceRequestId) voiceBusy.value = false;
  }
}

function stopVoiceRecording() {
  if (!voiceRecording.value) return;
  voiceRecording.value = false;
  if (recordTimer) {
    clearInterval(recordTimer);
    recordTimer = null;
  }
  recordingElapsedSec.value = Math.max(0, Math.round((Date.now() - recordStartedAt) / 1000));
  try {
    mediaRecorder?.stop();
  } catch (_) {
    stopVoiceStream();
  }
}

async function toggleFavorite(message) {
  if (!message || !message.mid || actionBusyMid.value) return;
  actionBusyMid.value = message.mid;
  try {
    const updated = message.is_favorite
      ? await unfavoriteChatMessage(message.mid)
      : await favoriteChatMessage(message.mid);
    upsertMessage(updated);
    queuePanelsRefresh();
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    actionBusyMid.value = "";
  }
}

async function recallMessage(message) {
  if (!message || !message.mid || actionBusyMid.value) return;
  actionBusyMid.value = message.mid;
  try {
    const updated = await recallChatMessage(message.mid);
    upsertMessage(updated);
    if (replyingTo.value?.mid === message.mid) clearReply();
    queuePanelsRefresh();
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    actionBusyMid.value = "";
  }
}

async function pinQuote(message) {
  if (!message || !message.mid || pinBusy.value) return;
  pinBusy.value = true;
  try {
    if (pinnedQuote.value && pinnedQuote.value.mid === message.mid) {
      await clearPinned();
      return;
    }
    const data = await setPinnedQuote(message.mid);
    pinnedQuote.value = normalizeMessage(data.message);
    showMessage(t('cottageChat.pinnedToast'));
    queuePanelsRefresh();
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    pinBusy.value = false;
  }
}

async function clearPinned() {
  if (pinBusy.value) return;
  pinBusy.value = true;
  try {
    await clearPinnedQuote();
    pinnedQuote.value = null;
    queuePanelsRefresh();
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    pinBusy.value = false;
  }
}

async function poke(kind) {
  if (pokeBusy.value) return;
  pokeBusy.value = true;
  try {
    await sendPoke(kind);
    const found = pokes.value.find((item) => item.kind === kind);
    showMessage(t('cottageChat.pokeSent', { name: partner.value.nickname || t('cottageChat.them'), action: found ? found.label : t('cottageChat.defaultPokeAction') }));
  } catch (error) {
    showMessage(parseError(error));
  } finally {
    setTimeout(() => {
      pokeBusy.value = false;
    }, 600);
  }
}

function flashPoke(text, emoji) {
  pokeFlash.value = { text, emoji: emoji || "💕" };
  if (pokeFlashTimer) clearTimeout(pokeFlashTimer);
  pokeFlashTimer = setTimeout(() => {
    pokeFlash.value = null;
  }, 2200);
}

// ── E2E chat actions ──────────────────────────────────────────────

function openE2EDialog() {
  e2ePassphrase.value = "";
  e2eDialogMode.value = chatE2EEnabled.value ? (isChatUnlocked() ? "rekey" : "unlock") : "setup";
  showE2EDialog.value = true;
}

async function submitE2EPassphrase() {
  if (e2eBusy.value) return;
  if (e2ePassphrase.value.length < 6) {
    showMessage(t("cottageChat.passphraseMinLength"));
    return;
  }
  e2eBusy.value = true;
  try {
    if (e2eDialogMode.value === "setup") {
      const { publicMeta } = await createChatKeySetup(e2ePassphrase.value);
      await setupChatKey(publicMeta);
      // Auto-unlock the freshly-created key so the next outgoing message
      // uses it without a second round-trip.
      const meta = await fetchChatKeyMeta();
      await unlockChatKey({ passphrase: e2ePassphrase.value, publicMeta: meta });
      chatE2EEnabled.value = true;
      chatE2EUnlocked.value = true;
      showMessage(t('cottageChat.e2eSetupToast'));
    } else if (e2eDialogMode.value === "unlock") {
      const meta = await fetchChatKeyMeta();
      await unlockChatKey({ passphrase: e2ePassphrase.value, publicMeta: meta });
      // Tell the server we have a live unlocked session.
      chatE2EUnlocked.value = true;
      showMessage(t('cottageChat.e2eUnlockToast'));
    } else if (e2eDialogMode.value === "rekey") {
      const { publicMeta } = await createChatKeySetup(e2ePassphrase.value);
      // Rekey endpoint takes the same shape as setup but rotates the
      // existing row in place (instead of returning 409).
      const rekeyed = await rekeyChatKey({
        ...publicMeta,
        new_salt: publicMeta.salt,
        new_verifier_iv: publicMeta.verifier_iv,
        new_verifier_cipher: publicMeta.verifier_cipher,
        new_verifier_hash: publicMeta.verifier_hash,
      });
      // Drop the cached CryptoKey (the old salt is no longer valid)
      // and immediately re-unlock under the fresh salt.
      clearChatSession();
      await unlockChatKey({ passphrase: e2ePassphrase.value, publicMeta: rekeyed });
      chatE2EUnlocked.value = true;
      showMessage(t("cottageChat.e2eRekeyToast"));
    }
    showE2EDialog.value = false;
    // Re-decrypt existing messages now that the key is available,
    // so the user doesn't have to leave and re-enter the page.
    redecryptMessages().catch(() => {});
  } catch (err) {
    showMessage(parseError(err));
  } finally {
    e2eBusy.value = false;
  }
}

function disableE2E() {
  // Local-only: the server row stays (a future setup is just a re-encrypt),
  // but the in-memory key is dropped and outgoing messages fall back to
  // plaintext. The partner will still see ciphertext on old messages,
  // so this is mostly useful when the user suspects a compromised device.
  clearChatSession();
  chatE2EUnlocked.value = false;
  showMessage(t('cottageChat.e2eDisabledToast'));
  showE2EDialog.value = false;
}

function clearPartnerTypingLater() {
  if (partnerTypingTimer) clearTimeout(partnerTypingTimer);
  partnerTypingTimer = setTimeout(() => {
    partnerTyping.value = { isTyping: false, at: null };
  }, 2500);
}

function onKeydown(evt) {
  if (evt.key === "Enter" && !evt.shiftKey) {
    evt.preventDefault();
    send();
  }
}

function handleEvent(event) {
  if (!componentAlive) return;
  if (!event || typeof event !== "object") return;
  if (event.type === "CHAT_MESSAGE") {
    // Decrypt is async but we render immediately with the placeholder
    // so the WS push latency never blocks the UI.
    const raw = normalizeMessage(event.payload || {});
    if (!raw) return;
    upsertMessage(raw);
    decryptIncoming(raw).then((decoded) => {
      if (!componentAlive) return;
      upsertMessage(decoded);
    });
    queuePanelsRefresh();
    if (!raw.is_self) markReadSafe();
  } else if (event.type === "CHAT_READ") {
    const at = event.payload && event.payload.read_at;
    for (const message of messages.value) {
      if (message.is_self && !message.read_at) message.read_at = at;
    }
  } else if (event.type === "PRESENCE") {
    if (event.payload && event.payload.uid === partner.value.uid) {
      partner.value = {
        ...partner.value,
        online: !!event.payload.online,
        onlineSince: event.payload.online_since || null,
        lastActiveAt: event.payload.last_active_at || partner.value.lastActiveAt,
      };
    }
  } else if (event.type === "PRESENCE_SNAPSHOT") {
    const online = (event.payload && event.payload.online) || [];
    if (partner.value.uid) {
      partner.value = { ...partner.value, online: online.includes(partner.value.uid) };
    }
  } else if (event.type === "TYPING") {
    if (event.payload?.uid === partner.value.uid) {
      partnerTyping.value = {
        isTyping: !!event.payload.is_typing,
        at: event.payload.at || null,
      };
      if (partnerTyping.value.isTyping) {
        clearPartnerTypingLater();
      }
    }
  } else if (event.type === "POKE") {
    const payload = event.payload || {};
    flashPoke(
      t('cottageLayout.pokeText', { name: payload.from_nickname || t('cottageChat.them'), label: payload.label || t('cottageLayout.defaultPokeLabel') }),
      POKE_EMOJI[payload.kind]
    );
  }
}

watch([draft, futureAtInput], saveDraftToStorage);

onMounted(async () => {
  componentAlive = true;
  const lifecycle = ++lifecycleGeneration;
  restoreDraftFromStorage();
  try {
    const me = await fetchMe();
    if (lifecycle !== lifecycleGeneration) return;
    myUid.value = me.uid;
  } catch (_) {
    if (lifecycle !== lifecycleGeneration) return;
  }
  try {
    const state = await fetchChatState();
    if (lifecycle !== lifecycleGeneration) return;
    applyPartnerState(state);
  } catch (_) {
    if (lifecycle !== lifecycleGeneration) return;
  }
  // Pull the E2E chat key state. The server only ever reveals the
  // KDF parameters + verifier to the owner user; partner users only
  // get the boolean "initialized" so they know whether they should
  // also turn E2E on (a future enhancement could expose a public
  // per-user KDF parameter to a partner who has already setup E2E).
  fetchChatKeyMeta()
    .then((meta) => {
      if (!componentAlive) return;
      chatE2EEnabled.value = !!meta?.initialized;
      chatE2EUnlocked.value = isChatUnlocked() && hasStoredChatSession();
    })
    .catch(() => {
      // Server unavailable or endpoint not migrated yet: use plaintext mode.
      // fall back to plaintext mode.
    });
  // Connect before fetching history. loadInitial merges any WS-first messages,
  // and every reconnect backfills events missed while the socket was down.
  socket = createCottageSocket({
    onEvent: handleEvent,
    onOpen: () => {
      if (componentAlive && lifecycle === lifecycleGeneration) void loadInitial();
    }
  });
  await loadInitial();
  if (lifecycle !== lifecycleGeneration) return;
  await loadPanels({ silent: true });
  if (lifecycle !== lifecycleGeneration) return;
  markReadSafe();
  nowTimer = setInterval(() => {
    nowTick.value = Date.now();
  }, 15000);
  nextTick(() => autoGrow());
});

onBeforeUnmount(() => {
  componentAlive = false;
  lifecycleGeneration += 1;
  messagesRequestGeneration += 1;
  voiceRequestId += 1;
  sendTyping(false);
  if (socket) socket.close();
  if (pokeFlashTimer) clearTimeout(pokeFlashTimer);
  if (panelsRefreshTimer) clearTimeout(panelsRefreshTimer);
  if (typingStopTimer) clearTimeout(typingStopTimer);
  if (partnerTypingTimer) clearTimeout(partnerTypingTimer);
  if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
  if (nowTimer) clearInterval(nowTimer);
  if (recordTimer) clearInterval(recordTimer);
  if (voiceRecording.value) {
    if (mediaRecorder) {
      mediaRecorder.ondataavailable = null;
      mediaRecorder.onstop = null;
    }
    try {
      mediaRecorder?.stop();
    } catch (_) {
      /* ignore */
    }
  }
  stopVoiceStream();
  clearVoiceDraft();
  // Revoke all decrypted media blob URLs and clear pending queue.
  pendingMediaQueue.length = 0;
  for (const url of Object.values(decryptedMediaUrls.value)) {
    URL.revokeObjectURL(url);
  }
  decryptedMediaUrls.value = {};
});
</script>

<style scoped>

/* Refined chat layout: secondary content lives in one collapsible drawer. */
.chat-shell {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 0.65rem;
  height: clamp(500px, calc(100dvh - 7.75rem), 880px);
  min-height: 0;
  margin-top: 1rem;
}

.chat-header,
.chat-tools,
.chat-room {
  border-radius: var(--radius-card);
}

.chat-header {
  display: flex;
  align-items: center;
  min-height: 62px;
  padding: 0.65rem 0.75rem;
  gap: 0.65rem;
  flex: 0 0 auto;
  box-shadow: 0 8px 22px rgb(39 57 50 / 0.06);
}

.chat-icon-btn {
  width: 36px;
  height: 36px;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  background: var(--surface-raised);
  color: var(--text-soft);
  cursor: pointer;
  text-decoration: none;
  transition: color 0.15s ease, border-color 0.15s ease, background 0.15s ease, transform 0.15s ease;
}

.chat-icon-btn:hover {
  color: var(--brand-strong);
  border-color: #efc3d1;
  background: var(--brand-soft);
}

.chat-icon-btn:active,
.chat-tools-toggle:active,
.chat-tool-tabs button:active,
.chat-send:active,
.chat-mini-btn:active,
.chat-action-btn:active {
  transform: scale(0.97);
}

.chat-icon-btn:disabled,
.chat-mini-btn:disabled,
.chat-action-btn:disabled,
.chat-send:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}

.chat-back {
  width: 38px;
  height: 38px;
  border-radius: var(--radius-control);
  font-size: inherit;
  color: var(--text-main);
  background: var(--surface-subtle);
}

.chat-peer {
  min-width: 0;
  flex: 1;
  display: flex;
  align-items: center;
  gap: 0.65rem;
}

.chat-peer-avatar {
  position: relative;
  width: 40px;
  height: 40px;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #9aa8a3;
  color: #fff;
  font-weight: 700;
}

.chat-peer-avatar.online {
  background: var(--brand);
}

.chat-peer-dot {
  position: absolute;
  right: -1px;
  bottom: -1px;
  width: 11px;
  height: 11px;
  border: 2px solid var(--surface-raised);
  border-radius: 50%;
  border-color: var(--surface-raised);
  background: #aebbb7;
}

.chat-peer-dot.online {
  background: var(--mint);
}

.chat-peer-name {
  margin: 0;
  color: var(--text-main);
  font-size: 0.96rem;
  font-weight: 700;
}

.chat-peer-status {
  margin: 0;
  max-width: 34ch;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-soft);
  font-size: 0.76rem;
}

.chat-peer-meta {
  min-width: 0;
}

.chat-peer-status.online {
  color: var(--mint);
}

.chat-header-actions {
  display: flex;
  align-items: center;
  gap: 0.35rem;
  flex: 0 0 auto;
}

.chat-security-btn {
  color: var(--text-soft);
  background: var(--surface-raised);
  border-color: var(--border-subtle);
}

.chat-security-btn.enabled {
  color: var(--brand-strong);
  background: var(--brand-soft);
  border-color: #efc3d1;
}

.chat-security-btn.locked {
  color: #93601e;
  border-color: #e8cfaa;
  background: #fff7e8;
}

.chat-nudge-emoji {
  font-size: 1.02rem;
  line-height: 1;
}

.chat-tools {
  position: relative;
  flex: 0 0 auto;
  box-shadow: none;
}

.chat-tools.open {
  border-color: #e7bdcb;
}

.chat-tools-toggle {
  width: 100%;
  min-height: 48px;
  display: flex;
  align-items: center;
  gap: 0.65rem;
  padding: 0.5rem 0.75rem;
  border: 0;
  border-radius: inherit;
  background: transparent;
  color: var(--text-main);
  text-align: left;
  cursor: pointer;
}

.chat-tools-icon {
  width: 32px;
  height: 32px;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-control);
  color: var(--brand-strong);
  background: var(--brand-soft);
}

.chat-tools-copy {
  min-width: 0;
  flex: 1;
  display: flex;
  align-items: baseline;
  gap: 0.6rem;
}

.chat-tools-copy strong {
  flex: 0 0 auto;
  font-size: 0.86rem;
}

.chat-tools-copy > span {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-soft);
  font-size: 0.76rem;
}

.chat-tools-chevron {
  flex: 0 0 auto;
  color: var(--text-soft);
  transition: transform 0.2s ease;
}

.chat-tools.open .chat-tools-chevron {
  transform: rotate(180deg);
}

.chat-tools-drawer {
  position: absolute;
  top: calc(100% + 0.4rem);
  left: 0;
  right: 0;
  z-index: 12;
  max-height: min(500px, calc(100dvh - 12rem));
  overflow-y: auto;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  background: var(--surface-raised);
  box-shadow: 0 18px 38px rgb(39 57 50 / 0.16);
}

.tools-expand-enter-active,
.tools-expand-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
  transform-origin: top;
}

.tools-expand-enter-from,
.tools-expand-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

.chat-tool-tabs {
  position: sticky;
  top: 0;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.35rem;
  padding: 0.55rem;
  border-bottom: 1px solid var(--border-subtle);
  background: rgb(255 255 255 / 0.96);
}

.chat-tool-tabs button {
  min-height: 42px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  padding: 0.45rem 0.65rem;
  border: 1px solid transparent;
  border-radius: var(--radius-control);
  background: transparent;
  color: var(--text-soft);
  font: inherit;
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
}

.chat-tool-tabs button:hover {
  background: var(--surface-subtle);
  color: var(--text-main);
}

.chat-tool-tabs button.active {
  color: var(--brand-strong);
  border-color: #efc3d1;
  background: var(--brand-soft);
}

.chat-tool-content {
  padding: 1rem;
}

.chat-tool-pane {
  display: grid;
  gap: 0.85rem;
}

.chat-panel-head {
  display: flex;
  justify-content: space-between;
  gap: 0.8rem;
  align-items: center;
}

.chat-panel-head h3,
.chat-panel-head p,
.chat-panel-empty,
.chat-quote p,
.chat-quote footer,
.chat-schedule-hint,
.chat-future-text,
.chat-future-meta {
  margin: 0;
}

.chat-panel-head h3 {
  color: var(--text-main);
  font-size: 0.95rem;
}

.chat-panel-head p {
  margin-top: 0.2rem;
  color: var(--text-soft);
  font-size: 0.76rem;
  line-height: 1.45;
}

.chat-mini-btn {
  min-height: 32px;
  padding: 0.35rem 0.7rem;
  border: 1px solid #efc3d1;
  border-radius: var(--radius-control);
  background: var(--brand-soft);
  color: var(--brand-strong);
  font-size: 0.74rem;
  font-weight: 600;
  white-space: nowrap;
  cursor: pointer;
}

.chat-refresh-btn,
.chat-close-btn {
  width: 32px;
  height: 32px;
}

.chat-panel-empty {
  color: var(--text-soft);
  font-size: 0.8rem;
  line-height: 1.55;
}

.chat-search-box {
  position: relative;
  display: flex;
  align-items: center;
  margin-bottom: 0.4rem;
}
.chat-search-input {
  width: 100%;
  padding-right: 2rem;
  font-size: 0.84rem;
}
.chat-search-spin {
  position: absolute;
  right: 0.6rem;
  color: var(--text-soft);
  animation: spin 0.8s linear infinite;
}
.chat-search-hint {
  margin: 0 0 0.5rem;
  font-size: 0.72rem;
  color: var(--text-soft);
  opacity: 0.8;
}
.chat-search-results {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  max-height: 280px;
  overflow-y: auto;
}
.chat-search-result {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  padding: 0.45rem 0.6rem;
  border-radius: 10px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: rgba(255, 255, 255, 0.6);
  cursor: pointer;
  text-align: left;
  transition: background 0.12s ease;
}
.chat-search-result:hover {
  background: rgba(167, 139, 250, 0.12);
}
.chat-search-result-who {
  flex: 0 0 auto;
  font-size: 0.74rem;
  color: var(--text-soft);
  min-width: 1.5rem;
}
.chat-search-result-text {
  flex: 1;
  min-width: 0;
  font-size: 0.82rem;
  color: #2f3754;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-weight: 500;
}
.chat-search-result-time {
  flex: 0 0 auto;
  font-size: 0.7rem;
  color: var(--text-soft);
  opacity: 0.7;
}

.chat-quote {
  margin: 0;
  padding: 0.75rem 0.85rem;
  border-left: 3px solid var(--brand);
  background: var(--surface-tint);
}

.chat-quote p {
  color: var(--text-main);
  font-size: 0.93rem;
  line-height: 1.6;
}

.chat-quote footer {
  margin-top: 0.4rem;
  color: var(--text-soft);
  font-size: 0.72rem;
}

.chat-memory-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0.5rem;
}

.chat-memory-stat {
  min-width: 0;
  padding: 0.6rem 0.7rem;
  border-radius: var(--radius-control);
  background: var(--surface-subtle);
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.chat-memory-value {
  color: var(--text-main);
  font-size: 1.1rem;
  font-weight: 700;
}

.chat-memory-label {
  color: var(--text-soft);
  font-size: 0.74rem;
}

.chat-memory-lines {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.55rem;
}

.chat-memory-lines p {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  margin: 0;
  padding-left: 0.7rem;
  border-left: 2px solid var(--border-strong);
}

.chat-memory-lines strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-main);
  font-size: 0.82rem;
  line-height: 1.5;
}

.chat-memory-lines span {
  color: var(--text-soft);
  font-size: 0.72rem;
}

.chat-keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 0.45rem;
}

.chat-keyword-chip {
  padding: 0.28rem 0.65rem;
  border-radius: var(--radius-control);
  background: var(--brand-soft);
  color: var(--brand-strong);
  font-size: 0.74rem;
}

.chat-schedule-field {
  max-width: 360px;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  color: var(--text-soft);
  font-size: 0.78rem;
}

.chat-datetime {
  padding: 0.65rem 0.75rem;
  border: 1px solid var(--border-strong);
  border-color: var(--border-strong);
  border-radius: var(--radius-control);
  color: var(--text-main);
  background: var(--surface-raised);
  font: inherit;
}

.chat-datetime:focus,
.chat-textarea:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgb(201 87 126 / 0.12);
}

.chat-future-list {
  max-height: 190px;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.5rem;
}

.chat-future-item {
  padding: 0.65rem 0.75rem;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  background: var(--surface-subtle);
}

.chat-future-text {
  color: var(--text-main);
  font-size: 0.84rem;
  line-height: 1.5;
  word-break: break-word;
}

.chat-schedule-hint,
.chat-future-meta {
  color: var(--text-soft);
  font-size: 0.74rem;
}

.chat-media-sections {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  border-top: 1px solid var(--border-subtle);
  border-left: 1px solid var(--border-subtle);
}

.chat-media-group {
  min-width: 0;
  min-height: 112px;
  padding: 0.75rem;
  border-right: 1px solid var(--border-subtle);
  border-bottom: 1px solid var(--border-subtle);
}

.chat-media-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.6rem;
  color: var(--text-main);
  font-size: 0.78rem;
}

.chat-media-head strong {
  color: var(--brand-strong);
  font-size: 0.76rem;
}

.chat-media-grid {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 0.35rem;
}

.chat-media-thumb {
  min-width: 0;
  aspect-ratio: 1;
  overflow: hidden;
  padding: 0;
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  background: var(--surface-subtle);
  cursor: pointer;
}

.chat-media-thumb img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.chat-media-voices,
.chat-media-favorites {
  display: grid;
  gap: 0.45rem;
}

.chat-media-voice {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 0.5rem;
  color: var(--text-soft);
  font-size: 0.72rem;
}

.chat-favorite-item {
  width: 100%;
  min-width: 0;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 0.5rem;
  padding: 0.45rem 0;
  border: 0;
  border-bottom: 1px solid var(--border-subtle);
  background: transparent;
  color: var(--text-main);
  text-align: left;
  cursor: pointer;
}

.chat-favorite-item:last-child {
  border-bottom: 0;
}

.chat-favorite-item span {
  color: var(--brand-strong);
  font-size: 0.72rem;
}

.chat-favorite-item strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.78rem;
}

.chat-room {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 10px 28px rgb(39 57 50 / 0.07);
}

.chat-list {
  min-height: 0;
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 0.8rem clamp(0.6rem, 2vw, 1.1rem) 0.6rem;
  background: #f7faf9;
  scrollbar-color: var(--border-strong) transparent;
  scrollbar-width: thin;
}

.chat-load-more {
  text-align: center;
  padding: 0.15rem 0 0.35rem;
}

.chat-load-btn {
  min-height: 30px;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  background: var(--surface-raised);
  color: var(--text-soft);
  padding: 0.3rem 0.8rem;
  font-size: 0.76rem;
  cursor: pointer;
}

.chat-load-hint {
  color: var(--text-soft);
  font-size: 0.74rem;
}

.chat-day {
  align-self: center;
  margin: 0.3rem 0;
  padding: 0.18rem 0.55rem;
  border-radius: 6px;
  background: var(--surface-subtle);
  color: var(--text-soft);
  font-size: 0.7rem;
}

.chat-unread-divider {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  margin: 0.45rem 0;
  color: var(--brand-strong);
  font-size: 0.72rem;
}

.chat-unread-divider::before,
.chat-unread-divider::after {
  content: "";
  height: 1px;
  flex: 1;
  background: #e7bdcb;
}

.chat-skeleton {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding: 1rem 0;
}

.chat-skeleton span {
  width: min(62%, 360px);
  height: 42px;
  border-radius: 12px;
  background: #eaf0ed;
}

.chat-skeleton span:nth-child(2) {
  width: min(48%, 280px);
  align-self: flex-end;
  background: #f6dfe7;
}

.chat-skeleton span:nth-child(3) {
  width: min(38%, 220px);
}

.chat-empty {
  flex: 1;
  min-height: 170px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.3rem;
  padding: 2rem 1rem;
  color: var(--text-soft);
  text-align: center;
}

.chat-empty svg {
  margin-bottom: 0.35rem;
  color: var(--brand);
}

.chat-empty strong {
  color: var(--text-main);
  font-size: 0.92rem;
}

.chat-empty span {
  font-size: 0.8rem;
}

.chat-row {
  max-width: 100%;
  display: flex;
  align-items: flex-end;
  gap: 0.45rem;
  padding: 0.14rem 0;
}

.chat-row.self {
  flex-direction: row-reverse;
}

.chat-bubble-avatar {
  width: 28px;
  height: 28px;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: #9aa8a3;
  color: #fff;
  font-size: 0.78rem;
  font-weight: 700;
}

.chat-bubble-wrap {
  max-width: min(76%, 560px);
  display: flex;
  flex-direction: column;
}

.chat-bubble {
  position: relative;
  padding: 0.58rem 0.78rem;
  border-color: var(--border-subtle);
  border-radius: 14px;
  border-bottom-left-radius: 4px;
  color: var(--text-main);
  background: var(--surface-raised);
  font-size: 0.92rem;
  line-height: 1.5;
  word-break: break-word;
  white-space: pre-wrap;
  box-shadow: 0 3px 10px rgb(39 57 50 / 0.04);
}

.chat-bubble.self {
  color: #fff;
  background: var(--brand);
  border-color: var(--brand);
  border-radius: 14px;
  border-bottom-right-radius: 4px;
  box-shadow: 0 5px 12px rgb(167 66 101 / 0.16);
}

.chat-bubble.media {
  overflow: hidden;
  padding: 3px;
  border: 1px solid var(--border-subtle);
  background: var(--surface-raised);
}

.chat-bubble-marks {
  display: flex;
  flex-wrap: wrap;
  gap: 0.3rem;
}

.chat-favorite-mark,
.chat-pinned-mark {
  display: inline-flex;
  align-items: center;
  gap: 0.22rem;
  margin: 0 0 0.35rem;
  padding: 0;
  border-radius: 0;
  background: transparent;
  color: inherit;
  font-size: 0.65rem;
  opacity: 0.78;
}

.chat-reply-preview {
  display: grid;
  gap: 0.1rem;
  margin: -0.15rem -0.2rem 0.45rem;
  padding: 0.4rem 0.5rem;
  border-left: 2px solid var(--brand);
  border-radius: 6px;
  background: var(--surface-subtle);
  color: var(--text-soft);
}

.chat-reply-preview.self {
  border-left-color: rgb(255 255 255 / 0.72);
  background: rgb(255 255 255 / 0.16);
  color: rgb(255 255 255 / 0.86);
}

.chat-reply-author {
  font-size: 0.66rem;
  font-weight: 700;
}

.chat-reply-text {
  max-width: 34ch;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.72rem;
}

.chat-voice-bubble {
  min-width: min(280px, 65vw);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.chat-audio {
  width: 100%;
  min-width: 0;
  height: 32px;
}

.chat-voice-duration {
  flex: 0 0 auto;
  font-size: 0.7rem;
}

.chat-meta {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  margin-top: 0.15rem;
  padding: 0 0.2rem;
}

.chat-meta.self,
.chat-actions.self {
  justify-content: flex-end;
}

.chat-time,
.chat-receipt {
  color: var(--text-soft);
  font-size: 0.66rem;
}

.chat-receipt {
  color: #89958f;
}

.chat-receipt.read {
  color: var(--brand-strong);
}

.chat-actions {
  min-height: 28px;
  display: flex;
  gap: 0.25rem;
  margin-top: 0.16rem;
  padding: 0 0.2rem;
  opacity: 0;
  transform: translateY(-2px);
  transition: opacity 0.15s ease, transform 0.15s ease;
}

.chat-row:hover .chat-actions,
.chat-row:focus-within .chat-actions {
  opacity: 1;
  transform: translateY(0);
}

.chat-action-btn {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  background: var(--surface-raised);
  color: var(--text-soft);
  cursor: pointer;
}

.chat-action-btn:hover {
  color: var(--brand-strong);
  border-color: #efc3d1;
  background: var(--brand-soft);
}

.chat-input {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.65rem;
  border-top: 1px solid var(--border-subtle);
  border-radius: 0;
  background: var(--surface-raised);
}

.chat-reply-bar,
.chat-voice-draft {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.55rem 0.65rem;
  border-radius: var(--radius-control);
  background: var(--surface-subtle);
}

.chat-reply-bar > div {
  min-width: 0;
  flex: 1;
  display: grid;
  gap: 0.1rem;
}

.chat-reply-bar span {
  color: var(--brand-strong);
  font-size: 0.7rem;
}

.chat-reply-bar strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-main);
  font-size: 0.78rem;
}

.chat-send-tip,
.chat-recording-tip {
  margin: 0;
  padding: 0 0.2rem;
  color: var(--brand-strong);
  font-size: 0.74rem;
}

.chat-voice-draft {
  flex-wrap: wrap;
}

.chat-voice-draft-main {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: var(--text-main);
  font-size: 0.78rem;
}

.chat-voice-pill {
  color: var(--brand-strong);
  font-weight: 600;
}

.chat-voice-draft .chat-audio {
  min-width: min(280px, 100%);
  flex: 1;
}

.chat-input-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.chat-attach-btn {
  width: 38px;
  height: 38px;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-control);
  background: var(--surface-subtle);
  color: var(--text-soft);
  cursor: pointer;
}

.chat-attach-btn:hover {
  color: var(--brand-strong);
  border-color: #efc3d1;
  background: var(--brand-soft);
}

.chat-attach-btn.busy {
  opacity: 0.55;
  cursor: progress;
}

.chat-attach-btn:disabled {
  opacity: 0.48;
  cursor: not-allowed;
}

.chat-attach-btn.recording {
  color: #fff;
  border-color: var(--brand);
  background: var(--brand);
}

.chat-loading-icon {
  animation: chat-spin 0.8s linear infinite;
}

@keyframes chat-spin {
  to { transform: rotate(360deg); }
}

.chat-textarea {
  min-width: 0;
  min-height: 38px;
  flex: 1;
  resize: none;
  overflow-y: hidden;
  scrollbar-width: none;
  max-height: 140px;
  padding: 0.55rem 0.75rem;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-control);
  background: #fbfcfc;
  color: var(--text-main);
  font-family: inherit;
  font-size: 0.92rem;
  line-height: 1.45;
}

.chat-textarea::-webkit-scrollbar {
  display: none;
}

.chat-textarea::placeholder {
  color: #7a8984;
}

.chat-send {
  min-width: 92px;
  height: 38px;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.38rem;
  border: 0;
  border-radius: var(--radius-control);
  background: var(--brand-strong);
  color: #fff;
  font-size: 0.9rem;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 6px 14px rgb(167 66 101 / 0.2);
}

.chat-image {
  display: block;
  max-width: 100%;
  max-height: 240px;
  border-radius: 10px;
  cursor: pointer;
}

.chat-recalled-text,
.chat-encrypted-placeholder {
  color: var(--text-soft);
  font-size: 0.84rem;
  font-style: italic;
}

.chat-bubble.recalled.self .chat-recalled-text,
.chat-bubble.self .chat-encrypted-placeholder {
  color: rgb(255 255 255 / 0.78);
}

.chat-encrypted-placeholder {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
  padding: 0.15rem 0;
}

.poke-flash {
  position: fixed;
  inset: 0;
  z-index: 60;
  pointer-events: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.poke-flash-emoji {
  font-size: 5rem;
  animation: poke-bounce 0.6s ease;
}

.poke-flash-text {
  margin-top: 0.5rem;
  padding: 0.4rem 1rem;
  border-radius: var(--radius-control);
  background: rgb(43 56 52 / 0.86);
  color: #fff;
  font-size: 0.9rem;
}

@keyframes poke-bounce {
  0% { transform: scale(0.3); opacity: 0; }
  50% { transform: scale(1.2); opacity: 1; }
  100% { transform: scale(1); }
}

.poke-pop-enter-active { transition: opacity 0.2s ease; }
.poke-pop-leave-active { transition: opacity 0.5s ease; }
.poke-pop-enter-from,
.poke-pop-leave-to { opacity: 0; }

.e2e-overlay {
  position: fixed;
  inset: 0;
  z-index: 70;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 1.5rem;
  background: rgb(43 56 52 / 0.52);
  backdrop-filter: blur(3px);
}

.e2e-card {
  width: 100%;
  max-width: 380px;
  display: grid;
  gap: 0.75rem;
  padding: 1.2rem 1.2rem 1rem;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-card);
  background: var(--surface-raised);
  box-shadow: 0 18px 42px rgb(39 57 50 / 0.22);
}

.e2e-title {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  color: var(--text-main);
  font-size: 1.05rem;
}

.e2e-hint {
  margin: 0;
  color: var(--text-soft);
  font-size: 0.82rem;
  line-height: 1.6;
}

.e2e-input {
  width: 100%;
  height: 38px;
  padding: 0.45rem 0.7rem;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-control);
  background: var(--surface-raised);
  color: var(--text-main);
  box-sizing: border-box;
  font-size: 0.9rem;
}

.e2e-input:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgb(201 87 126 / 0.12);
}

.e2e-cancel,
.e2e-confirm,
.e2e-disable {
  border: 0;
  border-radius: var(--radius-control);
  padding: 0.4rem 0.95rem;
  font-size: 0.85rem;
  cursor: pointer;
}

.e2e-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}

.e2e-cancel {
  background: var(--surface-subtle);
  color: var(--text-main);
}

.e2e-confirm {
  background: var(--brand-strong);
  color: #fff;
}

.e2e-disable {
  align-self: flex-start;
  padding-left: 0;
  background: transparent;
  color: #a1374d;
  font-size: 0.75rem;
  text-decoration: underline;
}

.e2e-cancel:disabled,
.e2e-confirm:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.e2e-pop-enter-active,
.e2e-pop-leave-active {
  transition: opacity 0.2s ease;
}

.e2e-pop-enter-from,
.e2e-pop-leave-to {
  opacity: 0;
}

@media (hover: none) {
  .chat-actions {
    opacity: 1;
    transform: none;
  }
}

@media (max-width: 768px) {
  .chat-shell {
    height: clamp(500px, calc(100dvh - 7.25rem), 820px);
    margin-top: 0.75rem;
  }

  .chat-header {
    min-height: 58px;
    padding: 0.55rem;
    gap: 0.45rem;
  }

  .chat-peer {
    gap: 0.45rem;
  }

  .chat-peer-avatar {
    width: 36px;
    height: 36px;
  }

  .chat-header-actions {
    gap: 0.22rem;
  }

  .chat-header-actions .chat-icon-btn {
    width: 34px;
    height: 34px;
  }

  .chat-tools-copy {
    display: grid;
    gap: 0.05rem;
  }

  .chat-tools-drawer {
    max-height: min(470px, calc(100dvh - 10.5rem));
  }

  .chat-tool-content {
    padding: 0.8rem;
  }

  .chat-memory-grid,
  .chat-future-list {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .chat-memory-lines,
  .chat-media-sections {
    grid-template-columns: 1fr;
  }

  .chat-media-grid {
    grid-template-columns: repeat(6, minmax(0, 1fr));
  }

  .chat-bubble-wrap {
    max-width: calc(100% - 2.2rem);
  }

  .chat-input-row {
    display: grid;
    grid-template-columns: 38px 38px 38px minmax(0, 1fr) 42px;
    align-items: center;
    gap: 0.35rem;
  }

  .chat-send {
    min-width: 0;
    width: 42px;
    padding: 0;
  }

  .chat-send span {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0 0 0 0);
    clip-path: inset(50%);
    white-space: nowrap;
  }
}

@media (max-width: 520px) {
  .chat-back {
    width: 34px;
    height: 34px;
  }

  .chat-peer-avatar {
    display: none;
  }

  .chat-peer-name {
    font-size: 0.88rem;
  }

  .chat-peer-status {
    max-width: 15ch;
    font-size: 0.68rem;
  }

  .chat-tool-tabs button {
    min-height: 44px;
    flex-direction: column;
    gap: 0.16rem;
    padding: 0.3rem;
    font-size: 0.7rem;
  }

  .chat-panel-head {
    align-items: flex-start;
  }

  .chat-memory-stat {
    padding: 0.5rem 0.6rem;
  }

  .chat-media-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .chat-list {
    padding-inline: 0.55rem;
  }

  .chat-bubble-wrap {
    max-width: calc(100% - 1.8rem);
  }

  .chat-bubble-avatar {
    width: 24px;
    height: 24px;
    font-size: 0.7rem;
  }

  .chat-input {
    padding: 0.55rem;
  }

  .chat-voice-draft .chat-audio {
    min-width: 100%;
  }
}

@media (max-width: 380px) {
  .chat-header-actions .chat-icon-btn {
    width: 31px;
    height: 31px;
  }

  .chat-tools-copy > span {
    max-width: 18ch;
  }

  .chat-input-row {
    grid-template-columns: 36px 36px 36px minmax(0, 1fr) 40px;
    gap: 0.25rem;
  }

  .chat-attach-btn {
    width: 36px;
    height: 36px;
  }

  .chat-send {
    width: 40px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .chat-icon-btn,
  .chat-tools-chevron,
  .chat-actions,
  .tools-expand-enter-active,
  .tools-expand-leave-active,
  .poke-flash-emoji,
  .chat-loading-icon {
    animation: none;
    transition: none;
  }
}
</style>
