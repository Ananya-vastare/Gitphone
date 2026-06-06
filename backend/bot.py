"""
bot.py — All Telegram bot handlers for GitPhone MVP.
Uses python-telegram-bot v21 (async, webhook mode).

ConversationHandler states:
  /start flow:   WAITING_TOKEN → WAITING_REPO → WAITING_BRANCH → end
  /files flow:   SELECTING_FILES → WAITING_MESSAGE → CONFIRM_COMMIT → end
"""

import os
from datetime import datetime, timezone
from typing import Optional
import channel_logger
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (ContextTypes,ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from telegram.constants import ParseMode

from supabase_service import (
    get_user_by_telegram_id,
    upsert_user,
    update_last_active,
    get_pending_files,
    get_staged_files_by_ids,
    mark_files_committed,
    insert_commit_log,
    get_recent_commits,
)
from github_service import github_service

# ── Conversation States ──────────────────────────────────────────────────────
WAITING_TOKEN = 0
WAITING_REPO = 1
WAITING_BRANCH = 2
SELECTING_FILES = 10
WAITING_MESSAGE = 11
CONFIRM_COMMIT = 12


# ── Helpers ──────────────────────────────────────────────────────────────────

def _format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"


def _time_ago(iso_str: str) -> str:
    """Convert ISO timestamp to human-readable 'X ago' string."""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - dt
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            return f"{seconds // 60} minutes ago"
        elif seconds < 86400:
            return f"{seconds // 3600} hours ago"
        else:
            return f"{seconds // 86400} days ago"
    except Exception:
        return "recently"


def _build_files_keyboard(staged_files: list[dict], selected: set[str]) -> InlineKeyboardMarkup:
    """Build inline keyboard for /files command with toggle checkboxes."""
    buttons = []
    for f in staged_files:
        file_id = f["id"]
        filepath = f["filepath"]
        size = _format_file_size(f.get("file_size", 0))
        checked = "✅" if file_id in selected else "☐"
        label = f"{checked}  {filepath}  {size}"
        buttons.append([InlineKeyboardButton(label, callback_data=f"FILE_TOGGLE:{file_id}")])

    # Bottom row: Select All + Done
    done_count = f" ({len(selected)})" if selected else ""
    buttons.append([
        InlineKeyboardButton("☑️ Select All", callback_data="FILE_SELECT_ALL"),
        InlineKeyboardButton(f"✅ Done{done_count}", callback_data="FILE_DONE"),
    ])
    return InlineKeyboardMarkup(buttons)


async def _check_registered(update: Update) -> Optional[dict]:
    """Return user row if registered and not banned, else None."""
    telegram_id = str(update.effective_user.id)
    user = get_user_by_telegram_id(telegram_id)
    if not user:
        await update.effective_message.reply_text(
            "👋 You're not registered yet!\n\n"
            "Use /start to set up your GitPhone account."
        )
        return None
    if user.get("status") == "banned":
        await update.effective_message.reply_text(
            "⛔ Your account has been suspended.\n"
            "Contact support if you think this is a mistake."
        )
        return None
    update_last_active(telegram_id)
    return user


# ── /start Handler ────────────────────────────────────────────────────────────

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    telegram_id = str(update.effective_user.id)
    user = get_user_by_telegram_id(telegram_id)

    if user:
        # Returning user
        pending = get_pending_files(telegram_id)
        recent = get_recent_commits(telegram_id, limit=1)
        last_active = _time_ago(user.get("last_active", ""))
        await update.message.reply_text(
            f"👋 Welcome back!\n\n"
            f"📦 {user['default_repo']} • {user['branch']}\n"
            f"🕐 Last active: {last_active}\n"
            f"📁 {len(pending)} file(s) staged\n\n"
            f"Use /files to commit, or /help for commands."
        )
        return ConversationHandler.END

    # New user — start onboarding
    context.user_data.clear()
    await update.message.reply_text(
        "👋 Welcome to *GitPhone!*\n\n"
        "Commit to GitHub from anywhere — right from your phone.\n\n"
        "Let's get you set up. I need a few things:\n\n"
        "📋 *Step 1/3* — Send me your *GitHub Fine-Grained PAT*\n"
        "_(Settings → Developer Settings → Fine-grained tokens)_\n\n"
        "The token needs *Contents: read & write* on your target repo.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Cancel", callback_data="COMMIT_CANCEL")
        ]])
    )
    return WAITING_TOKEN


async def waiting_token_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    token = update.message.text.strip()
    if not (token.startswith("ghp_") or token.startswith("github_pat_")):
        await update.message.reply_text(
            "❌ That doesn't look like a GitHub PAT.\n\n"
            "It should start with `ghp_` or `github_pat_`\n\n"
            "Try again or send /cancel",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_TOKEN

    context.user_data["github_token"] = token
    await update.message.reply_text(
        "✅ Token looks valid!\n\n"
        "📦 *Step 2/3* — Which GitHub repo should I commit to?\n"
        "Format: `username/repo-name`\n\n"
        "Example: `john/my-project`",
        parse_mode=ParseMode.MARKDOWN
    )
    return WAITING_REPO


async def waiting_repo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    repo = update.message.text.strip()

    # Basic format check
    if "/" not in repo or len(repo.split("/")) != 2:
        await update.message.reply_text(
            "❌ Invalid format. Use: `username/repo-name`\n\nTry again:",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_REPO

    # Validate token + repo access
    token = context.user_data.get("github_token")
    await update.message.reply_text("🔍 Checking repo access...")

    result = github_service.validate_token_and_repo(token, repo)
    if not result["ok"]:
        error = result.get("error", "unknown")
        if error == "invalid_token":
            await update.message.reply_text(
                "❌ GitHub token is invalid or expired.\n\n"
                "Please send a valid token again.\n\n"
                "Use /start to restart setup."
            )
            return ConversationHandler.END
        elif error == "repo_not_found":
            await update.message.reply_text(
                f"❌ Repo `{repo}` not found or your token has no access.\n\n"
                "Check the repo name and token permissions, then try again:",
                parse_mode=ParseMode.MARKDOWN
            )
            return WAITING_REPO
        else:
            await update.message.reply_text(
                f"❌ GitHub error: {result.get('message', 'Unknown error')}\n\nTry again:"
            )
            return WAITING_REPO

    context.user_data["default_repo"] = repo
    context.user_data["default_branch"] = result.get("default_branch", "main")

    await update.message.reply_text(
        f"✅ Repo found: `{repo}`\n\n"
        f"🌿 *Step 3/3* — What branch should I commit to?\n"
        f"_(Press Enter or type `main` to use the default)_\n\n"
        f"Detected default branch: `{result.get('default_branch', 'main')}`",
        parse_mode=ParseMode.MARKDOWN
    )
    return WAITING_BRANCH


async def waiting_branch_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    branch = update.message.text.strip() or context.user_data.get("default_branch", "main")
    telegram_id = str(update.effective_user.id)
    token = context.user_data["github_token"]
    repo = context.user_data["default_repo"]

    # Save user to Supabase
    user_data = {
        "telegram_id": telegram_id,
        "github_token": token,
        "default_repo": repo,
        "branch": branch,
    }
    saved = upsert_user(user_data)

    if not saved:
        await update.message.reply_text(
            "❌ Failed to save your configuration. Please try /start again."
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"✅ *All set!*\n\n"
        f"Your GitPhone is configured:\n"
        f"📦 `{repo}` • `{branch}`\n\n"
        f"Now install the VS Code extension and connect it with your Telegram ID:\n"
        f"👤 *Your ID:* `{telegram_id}`\n\n"
        f"Once the extension is installed, save any file in VS Code "
        f"and it will appear here via /files\n\n"
        f"Type /help to see all commands.",
        parse_mode=ParseMode.MARKDOWN
    )
    # Log new registration to channel
    await channel_logger.log_new_user(telegram_id, repo, branch)
    context.user_data.clear()
    return ConversationHandler.END


# ── /files Handler ────────────────────────────────────────────────────────────

async def files_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await _check_registered(update)
    if not user:
        return ConversationHandler.END

    telegram_id = str(update.effective_user.id)
    staged = get_pending_files(telegram_id)

    if not staged:
        await update.message.reply_text(
            "📭 *No files staged yet.*\n\n"
            "Save a file in VS Code and it will appear here automatically.\n\n"
            f"Your setup: `{user['default_repo']}` • `{user['branch']}`",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    # Store full staged data in session
    context.user_data["staged_data"] = {f["id"]: f for f in staged}
    context.user_data["selected_files"] = set()

    keyboard = _build_files_keyboard(staged, set())
    await update.message.reply_text(
        f"📁 *{user['default_repo']}* • `{user['branch']}`\n\n"
        f"Select files to commit:",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    return SELECTING_FILES


async def file_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    file_id = query.data.split(":", 1)[1]
    selected: set = context.user_data.get("selected_files", set())
    staged_data: dict = context.user_data.get("staged_data", {})

    # Toggle
    if file_id in selected:
        selected.discard(file_id)
    else:
        selected.add(file_id)
    context.user_data["selected_files"] = selected

    staged_files = list(staged_data.values())
    keyboard = _build_files_keyboard(staged_files, selected)

    user = get_user_by_telegram_id(str(update.effective_user.id))
    try:
        await query.edit_message_text(
            f"📁 *{user['default_repo']}* • `{user['branch']}`\n\n"
            f"Select files to commit:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        pass  # Message unchanged is fine

    return SELECTING_FILES


async def file_select_all_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    staged_data: dict = context.user_data.get("staged_data", {})
    selected = set(staged_data.keys())
    context.user_data["selected_files"] = selected

    staged_files = list(staged_data.values())
    keyboard = _build_files_keyboard(staged_files, selected)

    user = get_user_by_telegram_id(str(update.effective_user.id))
    try:
        await query.edit_message_text(
            f"📁 *{user['default_repo']}* • `{user['branch']}`\n\n"
            f"Select files to commit:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        pass

    return SELECTING_FILES


async def done_selecting_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    selected: set = context.user_data.get("selected_files", set())
    staged_data: dict = context.user_data.get("staged_data", {})

    if not selected:
        await query.answer("⚠️ No files selected. Tap files to toggle.", show_alert=True)
        return SELECTING_FILES

    # Build file list display
    selected_names = [staged_data[fid]["filepath"] for fid in selected if fid in staged_data]
    files_display = "\n".join(f"• `{f}`" for f in selected_names)

    await query.edit_message_text(
        f"✏️ *Type your commit message:*\n\n"
        f"Selected:\n{files_display}\n\n"
        f'_(e.g. "fix: updated auth logic")_',
        parse_mode=ParseMode.MARKDOWN
    )
    return WAITING_MESSAGE


async def commit_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.message.text.strip()
    if not message:
        await update.message.reply_text("⚠️ Commit message cannot be empty. Try again:")
        return WAITING_MESSAGE

    context.user_data["commit_message"] = message

    selected: set = context.user_data.get("selected_files", set())
    staged_data: dict = context.user_data.get("staged_data", {})
    selected_names = [staged_data[fid]["filepath"] for fid in selected if fid in staged_data]

    user = get_user_by_telegram_id(str(update.effective_user.id))
    files_display = "\n".join(f"• `{f}`" for f in selected_names)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🚀 Commit Now", callback_data="COMMIT_NOW"),
            InlineKeyboardButton("❌ Cancel", callback_data="COMMIT_CANCEL"),
        ]
    ])

    await update.message.reply_text(
        f"📦 *Review Commit*\n\n"
        f"Files:\n{files_display}\n\n"
        f"💬 `{message}`\n"
        f"🌿 `{user['branch']}` • `{user['default_repo']}`\n\n"
        f"Ready to commit?",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )
    return CONFIRM_COMMIT


async def commit_now_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⏳ Committing...")

    telegram_id = str(update.effective_user.id)
    user = get_user_by_telegram_id(telegram_id)
    if not user:
        await query.edit_message_text("❌ User not found. Please /start again.")
        return ConversationHandler.END

    selected: set = context.user_data.get("selected_files", set())
    staged_data: dict = context.user_data.get("staged_data", {})
    commit_message: str = context.user_data.get("commit_message", "GitPhone commit")

    file_ids = [fid for fid in selected if fid in staged_data]
    staged_rows = get_staged_files_by_ids(file_ids)

    if not staged_rows:
        await query.edit_message_text("❌ Could not load staged files. Try /files again.")
        return ConversationHandler.END

    # ── Call GitHub Service ──────────────────────────────────────────────
    result = github_service.commit_files(
        token=user["github_token"],
        repo_name=user["default_repo"],
        branch=user["branch"],
        staged_files=staged_rows,
        commit_message=commit_message,
    )

    if result["ok"]:
        commit_sha = result["commit_sha"]
        short_sha = commit_sha[:7] if commit_sha else "unknown"
        committed_files = [r["filepath"] for r in staged_rows]

        # Mark files as committed
        mark_files_committed(file_ids)

        # Log the commit
        insert_commit_log({
            "telegram_id": telegram_id,
            "user_id": user["id"],
            "commit_sha": commit_sha or "unknown",
            "message": commit_message,
            "files": committed_files,
            "repo": user["default_repo"],
            "branch": user["branch"],
            "was_scheduled": False,
        })

        # Log to channel
        await channel_logger.log_commit(
            telegram_id=telegram_id,
            repo=user["default_repo"],
            branch=user["branch"],
            commit_sha=commit_sha or "unknown",
            message=commit_message,
            files=committed_files,
            was_forced=False,
        )

        conflict_note = ""
        if result.get("conflict_files"):
            conflict_note = (
                f"\n\n⚠️ Skipped (conflict): "
                + ", ".join(f"`{f}`" for f in result["conflict_files"])
            )

        await query.edit_message_text(
            f"✅ *Committed!*\n\n"
            f"🔗 `{short_sha}`\n"
            f"💬 {commit_message}\n"
            f"🌿 `{user['branch']}` • `{user['default_repo']}`\n"
            f"🕐 Just now\n"
            f"🔥 Streak maintained!{conflict_note}",
            parse_mode=ParseMode.MARKDOWN
        )

    elif result.get("error") == "conflict":
        conflict_files = result.get("conflict_files", [])
        conflict_display = "\n".join(f"• `{f}`" for f in conflict_files)
        context.user_data["staged_rows_for_force"] = staged_rows
        context.user_data["file_ids_for_force"] = file_ids

        # Log conflict to channel
        await channel_logger.log_conflict(
            telegram_id=telegram_id,
            repo=user["default_repo"],
            conflict_files=conflict_files,
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Force Commit (overwrite)", callback_data="COMMIT_FORCE")],
            [InlineKeyboardButton("❌ Cancel", callback_data="COMMIT_CANCEL")],
        ])
        await query.edit_message_text(
            f"⚠️ *Conflict Detected*\n\n"
            f"{conflict_display}\n\n"
            f"These files were modified on GitHub after you staged them.\n\n"
            f"What would you like to do?",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return CONFIRM_COMMIT

    elif result.get("error") == "branch_protected":
        await channel_logger.log_commit_failed(telegram_id, user["default_repo"], "branch_protected")
        await query.edit_message_text(
            f"⚠️ *Branch is protected.*\n\n"
            f"`{user['branch']}` has branch protection rules.\n"
            f"GitPhone cannot push directly.\n\n"
            f"Configure your branch protection rules on GitHub to allow this token."
        )

    else:
        error_msg = result.get('message', 'Unknown error')
        await channel_logger.log_commit_failed(telegram_id, user["default_repo"], error_msg)
        await query.edit_message_text(
            f"❌ *Commit failed.*\n\n"
            f"Error: {error_msg}\n\n"
            f"Your staged files are safe. Try /files again."
        )

    context.user_data.clear()
    return ConversationHandler.END


async def commit_force_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Force commit — overwrite GitHub with staged version."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("⏳ Force committing...")

    telegram_id = str(update.effective_user.id)
    user = get_user_by_telegram_id(telegram_id)
    staged_rows = context.user_data.get("staged_rows_for_force", [])
    file_ids = context.user_data.get("file_ids_for_force", [])
    commit_message = context.user_data.get("commit_message", "GitPhone force commit")

    if not staged_rows or not user:
        await query.edit_message_text("❌ Session expired. Please try /files again.")
        return ConversationHandler.END

    result = github_service.force_commit_files(
        token=user["github_token"],
        repo_name=user["default_repo"],
        branch=user["branch"],
        staged_files=staged_rows,
        commit_message=commit_message,
    )

    if result["ok"]:
        commit_sha = result["commit_sha"]
        short_sha = commit_sha[:7] if commit_sha else "unknown"
        committed_files = [r["filepath"] for r in staged_rows]
        mark_files_committed(file_ids)
        insert_commit_log({
            "telegram_id": telegram_id,
            "user_id": user["id"],
            "commit_sha": commit_sha or "unknown",
            "message": commit_message,
            "files": committed_files,
            "repo": user["default_repo"],
            "branch": user["branch"],
            "was_scheduled": False,
        })
        # Log force commit to channel
        await channel_logger.log_commit(
            telegram_id=telegram_id,
            repo=user["default_repo"],
            branch=user["branch"],
            commit_sha=commit_sha or "unknown",
            message=commit_message,
            files=committed_files,
            was_forced=True,
        )
        await query.edit_message_text(
            f"✅ *Force committed!*\n\n"
            f"🔗 `{short_sha}`\n"
            f"💬 {commit_message}\n"
            f"🌿 `{user['branch']}` • `{user['default_repo']}`\n"
            f"🕐 Just now",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        error_msg = result.get('message', 'Unknown error')
        await channel_logger.log_commit_failed(telegram_id, user["default_repo"], error_msg)
        await query.edit_message_text(
            f"❌ Force commit failed: {error_msg}"
        )

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_commit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text(
        "✅ Cancelled.\nNo changes were made.\n\nUse /files to start a new commit."
    )
    return ConversationHandler.END


# ── /cancel Command ────────────────────────────────────────────────────────────

async def cancel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(
        "✅ Cancelled.\nNo changes were made.\n\nUse /files to start a new commit."
    )
    return ConversationHandler.END


# ── /log Command ──────────────────────────────────────────────────────────────

async def log_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await _check_registered(update)
    if not user:
        return

    commits = get_recent_commits(str(update.effective_user.id), limit=10)
    if not commits:
        await update.message.reply_text(
            "📭 No commits yet via GitPhone.\n\n"
            "Stage files in VS Code, then use /files to commit."
        )
        return

    lines = [f"📜 *Recent Commits* (`{user['default_repo']}`)\n"]
    for i, c in enumerate(commits, 1):
        short_sha = c["commit_sha"][:7]
        files_str = ", ".join(c.get("files", []))
        time_str = _time_ago(c.get("committed_at", ""))
        lines.append(
            f"{i}. `{short_sha}` — {time_str}\n"
            f"   {c['message']}\n"
            f"   _{files_str}_"
        )

    await update.message.reply_text(
        "\n\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(
                f"{user['default_repo']} on GitHub ↗",
                url=f"https://github.com/{user['default_repo']}/commits/{user['branch']}"
            )
        ]])
    )


# ── /status Command ────────────────────────────────────────────────────────────

async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await _check_registered(update)
    if not user:
        return

    telegram_id = str(update.effective_user.id)
    staged = get_pending_files(telegram_id)
    commits = get_recent_commits(telegram_id, limit=100)
    last_sync = _time_ago(user.get("last_active", ""))

    await update.message.reply_text(
        f"📊 *GitPhone Status*\n\n"
        f"👤 Registered: ✅\n"
        f"📦 Repo: `{user['default_repo']}`\n"
        f"🌿 Branch: `{user['branch']}`\n"
        f"🔗 GitHub: Connected ✅\n\n"
        f"📁 Staged files: {len(staged)} pending\n"
        f"🕐 Last sync: {last_sync}\n"
        f"📝 Total commits via GitPhone: {len(commits)}\n\n"
        f"VS Code Extension: Connected ✅\n"
        f"Last seen: {last_sync}",
        parse_mode=ParseMode.MARKDOWN
    )


# ── /help Command ──────────────────────────────────────────────────────────────

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🛠 *GitPhone Commands*\n\n"
        "/files   — Select staged files & commit\n"
        "/log     — Recent commit history\n"
        "/status  — Your connection status\n"
        "/start   — Setup or reconfigure\n"
        "/cancel  — Cancel current operation\n"
        "/help    — This message\n\n"
        "📖 Docs: github.com/ankittroy-21/gitphone\n\n"
        "💡 *Tip:* Save any file in VS Code "
        "and it appears in /files within seconds.",
        parse_mode=ParseMode.MARKDOWN
    )


# ── Conversation Handlers (exported to main.py) ────────────────────────────────

def build_start_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("start", start_handler)],
        states={
            WAITING_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, waiting_token_handler)],
            WAITING_REPO: [MessageHandler(filters.TEXT & ~filters.COMMAND, waiting_repo_handler)],
            WAITING_BRANCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, waiting_branch_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
        allow_reentry=True,
    )


def build_files_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("files", files_handler)],
        states={
            SELECTING_FILES: [
                CallbackQueryHandler(file_toggle_callback, pattern=r"^FILE_TOGGLE:"),
                CallbackQueryHandler(file_select_all_callback, pattern=r"^FILE_SELECT_ALL$"),
                CallbackQueryHandler(done_selecting_callback, pattern=r"^FILE_DONE$"),
            ],
            WAITING_MESSAGE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, commit_message_handler),
            ],
            CONFIRM_COMMIT: [
                CallbackQueryHandler(commit_now_callback, pattern=r"^COMMIT_NOW$"),
                CallbackQueryHandler(commit_force_callback, pattern=r"^COMMIT_FORCE$"),
                CallbackQueryHandler(cancel_commit_callback, pattern=r"^COMMIT_CANCEL$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
        allow_reentry=True,
    )

