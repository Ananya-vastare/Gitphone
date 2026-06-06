"""
channel_logger.py — Sends structured log messages to a private Telegram channel.

HOW TO SET UP:
  1. Create a private Telegram channel
  2. Add your bot as an Administrator (with "Post Messages" permission)
  3. Get the channel ID (forward any message to @userinfobot or use @getidsbot)
     Channel IDs look like: -1001234567890
  4. Set LOG_CHANNEL_ID env var to that value

EVENTS LOGGED:
  - 🆕 New user registered
  - ✅ Commit successful
  - 🔄 Force commit
  - ⚠️  Conflict detected
  - ❌ Commit failed
  - 📁 File staged (sync)
  - ⛔ User banned / unbanned
  - 📢 Broadcast sent
  - 🔴 Backend errors
"""

import os
import traceback
from datetime import datetime, timezone
from typing import Optional

# Global bot reference — set during startup in main.py
_bot = None


def init_logger(bot) -> None:
    """Call once from main.py with the telegram Bot instance."""
    global _bot
    _bot = bot


def _get_channel_id() -> Optional[str]:
    return os.environ.get("LOG_CHANNEL_ID", "").strip() or None


def _now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


async def _send(text: str) -> None:
    """Fire-and-forget send to log channel. Never raises."""
    channel_id = _get_channel_id()
    if not channel_id or not _bot:
        return
    try:
        await _bot.send_message(
            chat_id=channel_id,
            text=text,
            parse_mode="Markdown",
            disable_notification=True,   # silent — no phone buzz for each log
        )
    except Exception as e:
        # Log to console but never crash the main flow
        print(f"[channel_logger] Failed to send log: {e}")


# ── Event Loggers ─────────────────────────────────────────────────────────────

async def log_new_user(telegram_id: str, repo: str, branch: str) -> None:
    await _send(
        f"🆕 *New User Registered*\n"
        f"👤 `{telegram_id}`\n"
        f"📦 `{repo}` • `{branch}`\n"
        f"🕐 {_now_utc()}"
    )


async def log_commit(
    telegram_id: str,
    repo: str,
    branch: str,
    commit_sha: str,
    message: str,
    files: list[str],
    was_forced: bool = False,
) -> None:
    icon = "🔄" if was_forced else "✅"
    label = "Force Commit" if was_forced else "Commit"
    short_sha = commit_sha[:7] if commit_sha else "unknown"
    files_str = "\n".join(f"  • `{f}`" for f in files) or "  —"
    await _send(
        f"{icon} *{label} Successful*\n"
        f"👤 `{telegram_id}`\n"
        f"📦 `{repo}` • `{branch}`\n"
        f"🔗 `{short_sha}`\n"
        f"💬 {message}\n"
        f"📁 Files:\n{files_str}\n"
        f"🕐 {_now_utc()}"
    )


async def log_commit_failed(
    telegram_id: str,
    repo: str,
    error: str,
) -> None:
    await _send(
        f"❌ *Commit Failed*\n"
        f"👤 `{telegram_id}`\n"
        f"📦 `{repo}`\n"
        f"⚠️ `{error}`\n"
        f"🕐 {_now_utc()}"
    )


async def log_conflict(
    telegram_id: str,
    repo: str,
    conflict_files: list[str],
) -> None:
    files_str = "\n".join(f"  • `{f}`" for f in conflict_files) or "  —"
    await _send(
        f"⚠️ *Conflict Detected*\n"
        f"👤 `{telegram_id}`\n"
        f"📦 `{repo}`\n"
        f"🔀 Conflicting files:\n{files_str}\n"
        f"🕐 {_now_utc()}"
    )


async def log_file_staged(
    telegram_id: str,
    filepath: str,
    repo: str,
    file_size: int,
    is_binary: bool,
) -> None:
    size_kb = round(file_size / 1024, 1)
    binary_tag = " _(binary)_" if is_binary else ""
    await _send(
        f"📁 *File Staged*\n"
        f"👤 `{telegram_id}`\n"
        f"📦 `{repo}`\n"
        f"📄 `{filepath}`{binary_tag} — `{size_kb}KB`\n"
        f"🕐 {_now_utc()}"
    )


async def log_user_banned(
    admin_id: str,
    target_id: str,
    action: str,          # "banned" or "unbanned"
) -> None:
    icon = "⛔" if action == "banned" else "✅"
    await _send(
        f"{icon} *User {action.title()}*\n"
        f"🔑 Admin: `{admin_id}`\n"
        f"👤 Target: `{target_id}`\n"
        f"🕐 {_now_utc()}"
    )


async def log_broadcast(
    admin_id: str,
    sent: int,
    failed: int,
    preview: str,
) -> None:
    preview_truncated = (preview[:80] + "…") if len(preview) > 80 else preview
    await _send(
        f"📢 *Broadcast Sent*\n"
        f"🔑 Admin: `{admin_id}`\n"
        f"✅ Sent: `{sent}` | ❌ Failed: `{failed}`\n"
        f"💬 _{preview_truncated}_\n"
        f"🕐 {_now_utc()}"
    )


async def log_error(
    context: str,
    error: Exception,
    telegram_id: Optional[str] = None,
) -> None:
    tb = traceback.format_exc()
    tb_short = tb[-500:] if len(tb) > 500 else tb  # last 500 chars
    user_line = f"👤 `{telegram_id}`\n" if telegram_id else ""
    await _send(
        f"🔴 *Backend Error*\n"
        f"{user_line}"
        f"📍 `{context}`\n"
        f"⚠️ `{type(error).__name__}: {str(error)[:100]}`\n"
        f"```\n{tb_short}\n```\n"
        f"🕐 {_now_utc()}"
    )


async def log_startup(webhook_url: str) -> None:
    await _send(
        f"🚀 *GitPhone Backend Started*\n"
        f"🔗 Webhook: `{webhook_url}/webhook`\n"
        f"🕐 {_now_utc()}"
    )


async def log_shutdown() -> None:
    await _send(
        f"🛑 *GitPhone Backend Shutting Down*\n"
        f"🕐 {_now_utc()}"
    )
