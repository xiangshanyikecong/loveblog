# Love Journal - a private journal + blog + real-time interaction platform for couples.
# Copyright (C) 2026 Love Journal Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""Lightweight, dict-based internationalization for user-facing strings.

Supports three locales: ``zh-CN`` (default), ``en-US`` and ``ja-JP``.
No external dependencies - messages live in a plain Python dict and are
rendered with ``str.format``.
"""

from __future__ import annotations

from starlette.requests import Request

DEFAULT_LOCALE = "zh-CN"
SUPPORTED_LOCALES = ("zh-CN", "en-US", "ja-JP")

MESSAGES: dict[str, dict[str, str]] = {
    # ------------------------------------------------------------------ zh-CN
    "zh-CN": {
        # --- notification: event reminders ---
        "notification.event.reminder_today.title": "{title} 今天",
        "notification.event.reminder_today.body": "纪念日时间：{date}",
        "notification.event.reminder_days.title": "{title} {days} 天后",
        "notification.event.reminder_days.body": "纪念日时间：{date}",
        # --- notification: capsule ---
        "notification.capsule.unlocked_title": "时间胶囊已解锁",
        "notification.capsule.unlocked_body": "{author} 的胶囊已到开启时间，快去看看吧。",
        # --- notification: period care ---
        "notification.period.care_title": "{name} 的生理期预计{when}到来",
        "notification.period.care_body": "记得多关心 Ta，备好热水和温暖的陪伴～",
        "notification.period.today": "今天",
        "notification.period.days_later": "{days} 天后",
        # --- error.detail: generic HTTPException messages ---
        "error.not_found": "{resource}不存在",
        "error.no_permission": "没有权限",
        "error.no_permission_to": "没有权限{action}",
        "error.invalid_credentials": "用户名或密码错误",
        "error.account_banned": "账号已被禁用",
        "error.username_exists": "用户名已存在",
        "error.already_exists": "{name}已存在",
        "error.login_required": "需要登录",
        "error.invalid_idempotency_key": "无效的幂等键",
        "error.invalid_token": "无效的令牌",
        "error.session_revoked": "会话已撤销",
        "error.user_not_found": "用户不存在",
        "error.file_empty": "上传文件为空",
        "error.file_too_large": "文件过大",
        "error.no_file_selected": "未选择文件",
        "error.article_version_conflict": "文章已被更新，请刷新后重试。",
        "error.message_content_empty": "消息内容不能为空",
        "error.media_url_missing": "缺少媒体地址",
        "error.audio_duration_missing": "缺少语音时长",
        "error.encrypted_chat_no_plaintext": "加密聊天已启用，不能发送明文消息",
        "error.reply_message_not_found": "回复的消息不存在",
        "error.message_not_found": "消息不存在",
        "error.can_only_recall_own_message": "只能撤回自己的消息",
        "error.message_recall_window_expired": "这条消息已超过可撤回时间",
        "error.only_text_can_pin": "只有文字消息可以置顶",
        "error.no_partner_account": "还没有另一半账号",
        "error.vault_already_initialized": "保险箱已初始化",
        "error.vault_not_initialized": "请先初始化保险箱",
        "error.vault_entry_not_found": "条目不存在",
        "error.rekey_requires_all_entries": "重设口令需要提交全部条目的新密文",
        "error.watch_source_not_found": "片源不存在",
        "error.unsupported_video_type": "不支持的视频类型，仅支持：{types}",
        "error.video_file_too_large": "文件过大（上限 2GB）",
        "error.save_video_failed": "保存视频失败",
        "error.bookmark_limit_exceeded": "书签数量不能超过 200 个",
        "error.invalid_month_format": "month 需为 YYYY-MM 格式",
        "error.no_partner_for_payer": "还没有另一半，无法记到对方名下",
    },
    # ------------------------------------------------------------------ en-US
    "en-US": {
        # --- notification: event reminders ---
        "notification.event.reminder_today.title": "{title} today",
        "notification.event.reminder_today.body": "Anniversary date: {date}",
        "notification.event.reminder_days.title": "{title} in {days} days",
        "notification.event.reminder_days.body": "Anniversary date: {date}",
        # --- notification: capsule ---
        "notification.capsule.unlocked_title": "Time capsule unlocked",
        "notification.capsule.unlocked_body": "{author}'s capsule has reached its opening time, come take a look.",
        # --- notification: period care ---
        "notification.period.care_title": "{name}'s period is expected to arrive {when}",
        "notification.period.care_body": "Remember to care for them - prepare hot water and warm companionship~",
        "notification.period.today": "today",
        "notification.period.days_later": "in {days} days",
        # --- error.detail: generic HTTPException messages ---
        "error.not_found": "{resource} not found",
        "error.no_permission": "No permission",
        "error.no_permission_to": "No permission to {action}",
        "error.invalid_credentials": "Invalid username or password",
        "error.account_banned": "Account is banned",
        "error.username_exists": "Username already exists",
        "error.already_exists": "{name} already exists",
        "error.login_required": "Login required",
        "error.invalid_idempotency_key": "Invalid Idempotency-Key",
        "error.invalid_token": "Invalid token",
        "error.session_revoked": "Session revoked",
        "error.user_not_found": "User not found",
        "error.file_empty": "Uploaded file is empty",
        "error.file_too_large": "File is too large",
        "error.no_file_selected": "No file selected",
        "error.article_version_conflict": "Article has been updated, please refresh and try again.",
        "error.message_content_empty": "Message content cannot be empty",
        "error.media_url_missing": "Missing media URL",
        "error.audio_duration_missing": "Missing audio duration",
        "error.encrypted_chat_no_plaintext": "Encrypted chat is enabled, cannot send plaintext messages",
        "error.reply_message_not_found": "Reply target message does not exist",
        "error.message_not_found": "Message not found",
        "error.can_only_recall_own_message": "You can only recall your own messages",
        "error.message_recall_window_expired": "This message has exceeded the recall time window",
        "error.only_text_can_pin": "Only text messages can be pinned",
        "error.no_partner_account": "No partner account found",
        "error.vault_already_initialized": "Vault is already initialized",
        "error.vault_not_initialized": "Please initialize the vault first",
        "error.vault_entry_not_found": "Entry not found",
        "error.rekey_requires_all_entries": "Rekey requires submitting new ciphertext for all entries",
        "error.watch_source_not_found": "Watch source not found",
        "error.unsupported_video_type": "Unsupported video type, only supported: {types}",
        "error.video_file_too_large": "File is too large (limit 2GB)",
        "error.save_video_failed": "Failed to save video",
        "error.bookmark_limit_exceeded": "Bookmark count cannot exceed 200",
        "error.invalid_month_format": "month must be in YYYY-MM format",
        "error.no_partner_for_payer": "No partner found, cannot charge to their account",
    },
    # ------------------------------------------------------------------ ja-JP
    "ja-JP": {
        # --- notification: event reminders ---
        "notification.event.reminder_today.title": "{title} 今日",
        "notification.event.reminder_today.body": "記念日：{date}",
        "notification.event.reminder_days.title": "{title} {days}日後",
        "notification.event.reminder_days.body": "記念日：{date}",
        # --- notification: capsule ---
        "notification.capsule.unlocked_title": "タイムカプセルが開封されました",
        "notification.capsule.unlocked_body": "{author}さんのカプセルが開封時間になりました、見に行きましょう。",
        # --- notification: period care ---
        "notification.period.care_title": "{name}さんの生理期が{when}に来る予定です",
        "notification.period.care_body": "パートナーを気遣って、お湯と温かいサポートを用意してね～",
        "notification.period.today": "今日",
        "notification.period.days_later": "{days}日後",
        # --- error.detail: generic HTTPException messages ---
        "error.not_found": "{resource}が見つかりません",
        "error.no_permission": "権限がありません",
        "error.no_permission_to": "{action}する権限がありません",
        "error.invalid_credentials": "ユーザー名またはパスワードが正しくありません",
        "error.account_banned": "アカウントは無効化されています",
        "error.username_exists": "ユーザー名はすでに存在します",
        "error.already_exists": "{name}はすでに存在します",
        "error.login_required": "ログインが必要です",
        "error.invalid_idempotency_key": "無効な冪等キーです",
        "error.invalid_token": "無効なトークンです",
        "error.session_revoked": "セッションが取り消されました",
        "error.user_not_found": "ユーザーが見つかりません",
        "error.file_empty": "アップロードファイルが空です",
        "error.file_too_large": "ファイルが大きすぎます",
        "error.no_file_selected": "ファイルが選択されていません",
        "error.article_version_conflict": "記事が更新されました。更新して再試行してください。",
        "error.message_content_empty": "メッセージの内容は空にできません",
        "error.media_url_missing": "メディアURLが不足しています",
        "error.audio_duration_missing": "音声の長さが不足しています",
        "error.encrypted_chat_no_plaintext": "暗号化チャットが有効になっているため、平文メッセージを送信できません",
        "error.reply_message_not_found": "返信先のメッセージが存在しません",
        "error.message_not_found": "メッセージが見つかりません",
        "error.can_only_recall_own_message": "自分のメッセージのみ取り消せます",
        "error.message_recall_window_expired": "このメッセージは取り消し可能な時間を超過しています",
        "error.only_text_can_pin": "テキストメッセージのみピン留めできます",
        "error.no_partner_account": "パートナーアカウントが見つかりません",
        "error.vault_already_initialized": "金庫はすでに初期化されています",
        "error.vault_not_initialized": "先に金庫を初期化してください",
        "error.vault_entry_not_found": "エントリが見つかりません",
        "error.rekey_requires_all_entries": "パスフレーズの再設定には全エントリの新しい暗号文の送信が必要です",
        "error.watch_source_not_found": "動画ソースが見つかりません",
        "error.unsupported_video_type": "サポートされていない動画形式です、対応形式：{types}",
        "error.video_file_too_large": "ファイルが大きすぎます（上限2GB）",
        "error.save_video_failed": "動画の保存に失敗しました",
        "error.bookmark_limit_exceeded": "ブックマーク数は200を超えることはできません",
        "error.invalid_month_format": "month は YYYY-MM 形式である必要があります",
        "error.no_partner_for_payer": "パートナーが見つかりません、相手のアカウントに記帳できません",
    },
}


def get_message(key: str, locale: str = DEFAULT_LOCALE, **kwargs) -> str:
    """Look up a localized message by *key* and *locale*.

    Falls back to ``zh-CN`` when *locale* is unsupported, then to *key*
    itself when the key is missing entirely.  ``kwargs`` are interpolated
    into ``{placeholder}`` segments via ``str.format``.
    """
    locale_messages = MESSAGES.get(locale) or MESSAGES[DEFAULT_LOCALE]
    template = locale_messages.get(key)
    if template is None:
        template = MESSAGES[DEFAULT_LOCALE].get(key, key)
    if kwargs:
        return template.format(**kwargs)
    return template


def get_locale_from_request(request: Request) -> str:
    """Determine the best supported locale from the ``Accept-Language`` header.

    Parses quality values (``q=``) and matches against ``SUPPORTED_LOCALES``.
    Falls back to ``DEFAULT_LOCALE`` when the header is absent or matches
    nothing.
    """
    raw = request.headers.get("Accept-Language", "")
    if not raw:
        return DEFAULT_LOCALE

    parsed: list[tuple[str, float]] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if ";q=" in part:
            lang, q = part.split(";q=", 1)
            try:
                weight = float(q)
            except ValueError:
                weight = 1.0
        else:
            lang = part
            weight = 1.0
        parsed.append((lang.strip().lower(), weight))

    # Highest quality first; stable sort preserves original order on ties.
    parsed.sort(key=lambda item: item[1], reverse=True)

    for lang, _ in parsed:
        if lang in ("zh-cn", "zh"):
            return "zh-CN"
        if lang in ("en-us", "en"):
            return "en-US"
        if lang in ("ja-jp", "ja"):
            return "ja-JP"
        if lang.startswith("zh"):
            return "zh-CN"
        if lang.startswith("en"):
            return "en-US"
        if lang.startswith("ja"):
            return "ja-JP"

    return DEFAULT_LOCALE
