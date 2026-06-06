"""
bot.py — All Telegram bot handlers for GitPhone.
Uses python-telegram-bot v21 (async, webhook mode).

User Commands:
  /start   — Register (PAT flow) or welcome back
  /files   — Select staged files grouped by repo & commit
  /log     — Recent commit history
  /status  — Connection status & repo info
  /repo    — Show or switch active repo
  /branch  — Switch active branch
  /preview — Preview diffs before committing
  /unstage — Remove a specific file from staged
  /clear   — Clear all staged files (panic button)
  /auth    — Re-enter GitHub PAT (when token expires)
  /cancel  — Cancel current operation
  /help    — Show all commands

Admin Commands (ADMIN_TELEGRAM_IDS env var):
  /ban <id> [reason]  — Ban a user
  /unban <id>         — Unban a user
  /users [page]       — List all users
  /broadcast <msg>    — Message all users
  /stats              — Global platform stats
  /revoke <id>        — Force user to re-authenticate
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
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
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
    get_pending_files_by_repo,
    get_staged_files_by_ids,
    mark_files_committed,
    insert_commit_log,
    get_recent_commits,
    unstage_file_by_path,
    clear_all_staged,
    update_branch,
    ban_user,
    unban_user,
    revoke_api_key,
    get_all_users,
    count_stats,
)
from github_service import github_service

# ── Conversation States ──────────────────────────────────────────────────────
WAITING_TOKEN = 0
WAITING_REPO = 1
WAITING_BRANCH = 2
SELECTING_FILES = 10
WAITING_MESSAGE = 11
CONFIRM_COMMIT = 12
WAITING_NEW_BRANCH = 20
WAITING_AUTH_TOKEN = 30

# ── Admin check ──────────────────────────────────────────────────────────────
def _is_admin(telegram_id: str) -> bool:
    admin_ids = os.environ.get("ADMIN_TELEGRAM_IDS", "").split(",")
    return telegram_id.strip() in [a.strip() for a in admin_ids if a.strip()]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _format_file_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes}B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f}KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f}MB"


def _time_ago(iso_str: str) -> str:
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - dt
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            return f"{seconds // 60}m ago"
        elif seconds < 86400:
            return f"{seconds // 3600}h ago"
        else:
            return f"{seconds // 86400}d ago"
    except Exception:
        return "recently"


def _build_files_keyboard(staged_files: list[dict], selected: set[str]) -> InlineKeyboardMarkup:
    """Build inline keyboard for file selection with change type icons."""
    buttons = []
    for f in staged_files:
        file_id = f["id"]
        filepath = f["filepath"]
        size = _format_file_size(f.get("file_size", 0))
        checked = "\u2705" if file_id in selected else "\u2610"
        # Show change type
        change = f.get("change_type", "modify")
        if change == "create":
            type_icon = "\u2795"   # ➕ new file
        elif change == "delete":
            type_icon = "\U0001f5d1"  # 🗑️ deletion
        else:
            type_icon = "\u270f"   # ✏️ modification
        label = f"{checked} {type_icon} {filepath}" + (f"  {size}" if size != "0B" else "")
        buttons.append([InlineKeyboardButton(label, callback_data=f"FILE_TOGGLE:{file_id}")])

    done_count = f" ({len(selected)})" if selected else ""
    buttons.append([
        InlineKeyboardButton("\u2611\ufe0f Select All", callback_data="FILE_SELECT_ALL"),
        InlineKeyboardButton(f"\u2705 Done{done_count}", callback_data="FILE_DONE"),
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

    if user and user.get("status") != "banned":
        pending = get_pending_files(telegram_id)
        last_active = _time_ago(user.get("last_active", ""))
        active_repo = user.get("active_repo") or user.get("default_repo", "—")
        active_branch = user.get("active_branch") or user.get("branch", "main")
        await update.message.reply_text(
            f"👋 Welcome back!\n\n"
            f"📦 `{active_repo}` • `{active_branch}`\n"
            f"🕐 Last active: {last_active}\n"
            f"📁 {len(pending)} file(s) staged\n\n"
            f"Use /files to commit, or /help for all commands.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    # New user — onboarding
    context.user_data.clear()
    await update.message.reply_text(
        "👋 Welcome to *GitPhone!*\n\n"
        "Commit to GitHub from anywhere — right from your phone.\n\n"
        "📋 *Step 1/3* — Send me your *GitHub Fine-Grained PAT*\n"
        "_(Settings → Developer Settings → Fine-grained tokens)_\n\n"
        "The token needs *Contents: read & write* on your target repo.\n\n"
        "👤 Your Telegram ID is: `" + telegram_id + "`\n"
        "_(You'll need this for the VS Code extension)_",
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
        "✅ Token saved!\n\n"
        "📦 *Step 2/3* — Which GitHub repo should I commit to?\n"
        "Format: `username/repo-name`\n\n"
        "Example: `john/my-project`",
        parse_mode=ParseMode.MARKDOWN
    )
    return WAITING_REPO


async def waiting_repo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    repo = update.message.text.strip()
    if "/" not in repo or len(repo.split("/")) != 2:
        await update.message.reply_text(
            "❌ Invalid format. Use: `username/repo-name`\n\nTry again:",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_REPO

    token = context.user_data.get("github_token")
    await update.message.reply_text("🔍 Checking repo access...")

    result = github_service.validate_token_and_repo(token, repo)
    if not result["ok"]:
        error = result.get("error", "unknown")
        if error == "invalid_token":
            await update.message.reply_text(
                "❌ GitHub token is invalid or expired.\n\nUse /start to restart setup."
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
        f"_(Detected default: `{result.get('default_branch', 'main')}`)_\n\n"
        f"Press Enter or type the branch name:",
        parse_mode=ParseMode.MARKDOWN
    )
    return WAITING_BRANCH


async def waiting_branch_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    branch = update.message.text.strip() or context.user_data.get("default_branch", "main")
    telegram_id = str(update.effective_user.id)
    token = context.user_data["github_token"]
    repo = context.user_data["default_repo"]

    user_data = {
        "telegram_id": telegram_id,
        "github_token": token,
        "default_repo": repo,
        "branch": branch,
        "active_repo": repo,
        "active_branch": branch,
    }
    saved = upsert_user(user_data)

    if not saved:
        await update.message.reply_text("❌ Failed to save configuration. Please try /start again.")
        return ConversationHandler.END

    await update.message.reply_text(
        f"✅ *All set!*\n\n"
        f"Your GitPhone is configured:\n"
        f"📦 `{repo}` • `{branch}`\n\n"
        f"Now connect the VS Code extension with your Telegram ID:\n"
        f"👤 *Your ID:* `{telegram_id}`\n\n"
        f"Install the extension → Open Setup → paste this ID.\n\n"
        f"Type /help to see all commands.",
        parse_mode=ParseMode.MARKDOWN
    )
    await channel_logger.log_new_user(telegram_id, repo, branch)
    context.user_data.clear()
    return ConversationHandler.END


# ── /auth Handler — Re-enter GitHub PAT ──────────────────────────────────────

async def auth_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await _check_registered(update)
    if not user:
        return ConversationHandler.END

    await update.message.reply_text(
        "🔑 *Re-authenticate GitHub*\n\n"
        "Your current token may have expired or lost access.\n\n"
        "Send me a new GitHub Fine-Grained PAT:\n"
        "_(Settings → Developer Settings → Fine-grained tokens)_\n\n"
        "Needs *Contents: read & write* on your repo.\n\n"
        "Or /cancel to keep the existing token.",
        parse_mode=ParseMode.MARKDOWN
    )
    return WAITING_AUTH_TOKEN


async def auth_token_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    token = update.message.text.strip()
    telegram_id = str(update.effective_user.id)

    if not (token.startswith("ghp_") or token.startswith("github_pat_")):
        await update.message.reply_text(
            "❌ Token must start with `ghp_` or `github_pat_`\n\nTry again or /cancel",
            parse_mode=ParseMode.MARKDOWN
        )
        return WAITING_AUTH_TOKEN

    user = get_user_by_telegram_id(telegram_id)
    repo = user.get("default_repo", "")

    await update.message.reply_text("🔍 Validating token...")
    result = github_service.validate_token_and_repo(token, repo)
    if not result["ok"]:
        await update.message.reply_text(
            f"❌ Token validation failed: {result.get('message', 'unknown error')}\n\n"
            "Try a different token or /cancel"
        )
        return WAITING_AUTH_TOKEN

    upsert_user({"telegram_id": telegram_id, "github_token": token})
    await update.message.reply_text(
        "✅ *GitHub token updated!*\n\n"
        "Your commits will now use the new token.\n"
        "Use /files to commit staged files.",
        parse_mode=ParseMode.MARKDOWN
    )
    return ConversationHandler.END


# ── /repo Handler ─────────────────────────────────────────────────────────────

async def repo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await _check_registered(update)
    if not user:
        return

    active_repo = user.get("active_repo") or user.get("default_repo", "—")
    active_branch = user.get("active_branch") or user.get("branch", "main")
    default_repo = user.get("default_repo", "—")
    is_auto = bool(user.get("active_repo") and user.get("active_repo") != default_repo)

    source_note = "🔄 Auto-detected from VS Code" if is_auto else "📌 Set in configuration"

    await update.message.reply_text(
        f"📦 *Active Repository*\n\n"
        f"`{active_repo}` • `{active_branch}`\n"
        f"{source_note}\n\n"
        f"📌 Default repo: `{default_repo}`\n\n"
        f"_Open a different project in VS Code and save a file — "
        f"GitPhone will auto-switch to that repo._\n\n"
        f"Use /branch to switch branch.",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(
                f"View on GitHub ↗",
                url=f"https://github.com/{active_repo}"
            )
        ]])
    )


# ── /branch Handler ───────────────────────────────────────────────────────────

async def branch_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await _check_registered(update)
    if not user:
        return ConversationHandler.END

    current = user.get("active_branch") or user.get("branch", "main")
    args = context.args

    if args:
        # /branch main — inline switch
        new_branch = args[0].strip()
        update_branch(str(update.effective_user.id), new_branch)
        await update.message.reply_text(
            f"✅ Branch switched to `{new_branch}`\n\n"
            f"Future commits will go to `{new_branch}`.",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"🌿 *Current Branch:* `{current}`\n\n"
        f"Type the branch name to switch, or /cancel:",
        parse_mode=ParseMode.MARKDOWN
    )
    return WAITING_NEW_BRANCH


async def branch_name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    new_branch = update.message.text.strip()
    telegram_id = str(update.effective_user.id)

    if not new_branch or " " in new_branch:
        await update.message.reply_text("❌ Invalid branch name. Try again or /cancel")
        return WAITING_NEW_BRANCH

    update_branch(telegram_id, new_branch)
    await update.message.reply_text(
        f"✅ Branch switched to `{new_branch}`\n\n"
        f"Future commits will go to `{new_branch}`.",
        parse_mode=ParseMode.MARKDOWN
    )
    return ConversationHandler.END


# ── /unstage Handler ──────────────────────────────────────────────────────────

async def unstage_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await _check_registered(update)
    if not user:
        return

    telegram_id = str(update.effective_user.id)
    args = context.args

    if not args:
        staged = get_pending_files(telegram_id)
        if not staged:
            await update.message.reply_text("📭 No staged files to unstage.")
            return

        file_list = "\n".join(f"• `{f['filepath']}`" for f in staged[:20])
        await update.message.reply_text(
            f"📁 *Staged Files:*\n\n{file_list}\n\n"
            f"Usage: `/unstage src/filename.py`",
            parse_mode=ParseMode.MARKDOWN
        )
        return

    filepath = " ".join(args).strip()
    found = unstage_file_by_path(telegram_id, filepath)

    if found:
        await update.message.reply_text(
            f"✅ Unstaged: `{filepath}`\n\n"
            f"The file was removed from your staged list.\n"
            f"It will be re-staged next time you save it in VS Code.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(
            f"❌ File not found in staged list: `{filepath}`\n\n"
            f"Use /unstage without arguments to see staged files.",
            parse_mode=ParseMode.MARKDOWN
        )


# ── /clear Handler ────────────────────────────────────────────────────────────

async def clear_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await _check_registered(update)
    if not user:
        return

    telegram_id = str(update.effective_user.id)
    staged = get_pending_files(telegram_id)

    if not staged:
        await update.message.reply_text("📭 No staged files to clear.")
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"🗑️ Clear All ({len(staged)} files)", callback_data="CLEAR_CONFIRM"),
            InlineKeyboardButton("❌ Cancel", callback_data="COMMIT_CANCEL"),
        ]
    ])
    await update.message.reply_text(
        f"⚠️ *Clear All Staged Files?*\n\n"
        f"This will remove all {len(staged)} staged file(s).\n"
        f"This cannot be undone.\n\n"
        f"Your actual files are safe — only the staged diffs are cleared.",
        reply_markup=keyboard,
        parse_mode=ParseMode.MARKDOWN
    )


async def clear_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    telegram_id = str(update.effective_user.id)
    count = clear_all_staged(telegram_id)
    await query.edit_message_text(
        f"✅ Cleared {count} staged file(s).\n\n"
        f"Save files in VS Code to re-stage them."
    )


# ── /preview Handler ──────────────────────────────────────────────────────────

async def preview_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = await _check_registered(update)
    if not user:
        return

    telegram_id = str(update.effective_user.id)
    staged = get_pending_files(telegram_id)

    if not staged:
        await update.message.reply_text(
            "📭 No staged files to preview.\n\n"
            "Save files in VS Code to stage them."
        )
        return

    # Show diff snippets for first 5 files
    lines = [f"👁 *Diff Preview* — {len(staged)} file(s) staged\n"]
    for f in staged[:5]:
        filepath = f["filepath"]
        size = _format_file_size(f.get("file_size", 0))
        diff = f.get("diff", "")

        # Show first 8 diff lines
        if diff:
            diff_lines = diff.split("\n")[:8]
            snippet = "\n".join(diff_lines)
            # Truncate if too long
            if len(snippet) > 300:
                snippet = snippet[:300] + "..."
        else:
            snippet = "(binary file)"

        lines.append(f"`{filepath}` ({size})\n```\n{snippet}\n```")

    if len(staged) > 5:
        lines.append(f"_...and {len(staged) - 5} more file(s)_")

    lines.append("\nUse /files to select and commit.")

    await update.message.reply_text(
        "\n\n".join(lines),
        parse_mode=ParseMode.MARKDOWN
    )


# ── /files Handler (grouped by repo) ─────────────────────────────────────────

async def files_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = await _check_registered(update)
    if not user:
        return ConversationHandler.END

    telegram_id = str(update.effective_user.id)
    grouped = get_pending_files_by_repo(telegram_id)

    if not grouped:
        active_repo = user.get("active_repo") or user.get("default_repo", "—")
        active_branch = user.get("active_branch") or user.get("branch", "main")
        await update.message.reply_text(
            "📭 *No files staged yet.*\n\n"
            "Save a file in VS Code and it will appear here automatically.\n\n"
            f"Active: `{active_repo}` • `{active_branch}`",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    # Build flat list with repo context
    all_files = []
    for repo, files in grouped.items():
        for f in files:
            f["_repo"] = repo  # tag each file with its repo
            all_files.append(f)

    context.user_data["staged_data"] = {f["id"]: f for f in all_files}
    context.user_data["selected_files"] = set()

    # Build header showing repos
    if len(grouped) == 1:
        repo_name = list(grouped.keys())[0]
        branch = user.get("active_branch") or user.get("branch", "main")
        header = f"📁 *{repo_name}* • `{branch}`\n\nSelect files to commit:"
    else:
        repo_summary = "\n".join(
            f"  📦 `{r}` — {len(files)} file(s)"
            for r, files in grouped.items()
        )
        header = f"📁 *{len(grouped)} Repos* staged:\n{repo_summary}\n\nSelect files to commit:"

    keyboard = _build_files_keyboard(all_files, set())
    await update.message.reply_text(
        header,
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

    if file_id in selected:
        selected.discard(file_id)
    else:
        selected.add(file_id)
    context.user_data["selected_files"] = selected

    staged_files = list(staged_data.values())
    keyboard = _build_files_keyboard(staged_files, selected)

    user = get_user_by_telegram_id(str(update.effective_user.id))
    active_repo = user.get("active_repo") or user.get("default_repo", "—")
    branch = user.get("active_branch") or user.get("branch", "main")
    try:
        await query.edit_message_text(
            f"📁 *{active_repo}* • `{branch}`\n\nSelect files to commit:",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
    except Exception:
        pass
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
    active_repo = user.get("active_repo") or user.get("default_repo", "—")
    branch = user.get("active_branch") or user.get("branch", "main")
    try:
        await query.edit_message_text(
            f"📁 *{active_repo}* • `{branch}`\n\nSelect files to commit:",
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
    active_repo = user.get("active_repo") or user.get("default_repo", "—")
    branch = user.get("active_branch") or user.get("branch", "main")
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
        f"🌿 `{branch}` • `{active_repo}`\n\n"
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

    # Use active_repo for commit target
    active_repo = user.get("active_repo") or user.get("default_repo")
    active_branch = user.get("active_branch") or user.get("branch", "main")

    selected: set = context.user_data.get("selected_files", set())
    staged_data: dict = context.user_data.get("staged_data", {})
    commit_message: str = context.user_data.get("commit_message", "GitPhone commit")

    file_ids = [fid for fid in selected if fid in staged_data]
    staged_rows = get_staged_files_by_ids(file_ids)

    if not staged_rows:
        await query.edit_message_text("❌ Could not load staged files. Try /files again.")
        return ConversationHandler.END

    result = github_service.commit_files(
        token=user["github_token"],
        repo_name=active_repo,
        branch=active_branch,
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
            "repo": active_repo,
            "branch": active_branch,
            "was_scheduled": False,
        })

        await channel_logger.log_commit(
            telegram_id=telegram_id,
            repo=active_repo,
            branch=active_branch,
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
            f"🔗 [`{short_sha}`](https://github.com/{active_repo}/commit/{commit_sha})\n"
            f"💬 {commit_message}\n"
            f"🌿 `{active_branch}` • `{active_repo}`\n"
            f"🕐 Just now{conflict_note}",
            parse_mode=ParseMode.MARKDOWN
        )

    elif result.get("error") == "conflict":
        conflict_files = result.get("conflict_files", [])
        conflict_display = "\n".join(f"• `{f}`" for f in conflict_files)
        context.user_data["staged_rows_for_force"] = staged_rows
        context.user_data["file_ids_for_force"] = file_ids

        await channel_logger.log_conflict(
            telegram_id=telegram_id,
            repo=active_repo,
            conflict_files=conflict_files,
        )

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Force Commit (overwrite)", callback_data="COMMIT_FORCE")],
            [InlineKeyboardButton("❌ Cancel", callback_data="COMMIT_CANCEL")],
        ])
        await query.edit_message_text(
            f"⚠️ *Conflict Detected*\n\n"
            f"{conflict_display}\n\n"
            f"These files were modified on GitHub after staging.\n\n"
            f"What would you like to do?",
            reply_markup=keyboard,
            parse_mode=ParseMode.MARKDOWN
        )
        return CONFIRM_COMMIT

    elif result.get("error") == "branch_protected":
        await channel_logger.log_commit_failed(telegram_id, active_repo, "branch_protected")
        await query.edit_message_text(
            f"⚠️ *Branch is protected.*\n\n"
            f"`{active_branch}` has branch protection rules.\n"
            f"GitPhone cannot push directly.\n\n"
            f"Use /branch to switch to a non-protected branch."
        )

    else:
        error_msg = result.get('message', 'Unknown error')
        await channel_logger.log_commit_failed(telegram_id, active_repo, error_msg)
        await query.edit_message_text(
            f"❌ *Commit failed.*\n\n"
            f"Error: {error_msg}\n\n"
            f"Your staged files are safe. Try /files again."
        )

    context.user_data.clear()
    return ConversationHandler.END


async def commit_force_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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

    active_repo = user.get("active_repo") or user.get("default_repo")
    active_branch = user.get("active_branch") or user.get("branch", "main")

    result = github_service.force_commit_files(
        token=user["github_token"],
        repo_name=active_repo,
        branch=active_branch,
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
            "repo": active_repo,
            "branch": active_branch,
            "was_scheduled": False,
        })
        await channel_logger.log_commit(
            telegram_id=telegram_id,
            repo=active_repo,
            branch=active_branch,
            commit_sha=commit_sha or "unknown",
            message=commit_message,
            files=committed_files,
            was_forced=True,
        )
        await query.edit_message_text(
            f"✅ *Force committed!*\n\n"
            f"🔗 `{short_sha}`\n"
            f"💬 {commit_message}\n"
            f"🌿 `{active_branch}` • `{active_repo}`",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        error_msg = result.get('message', 'Unknown error')
        await channel_logger.log_commit_failed(telegram_id, active_repo, error_msg)
        await query.edit_message_text(f"❌ Force commit failed: {error_msg}")

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

    active_repo = user.get("active_repo") or user.get("default_repo", "—")
    lines = [f"📜 *Recent Commits* (`{active_repo}`)\n"]
    for i, c in enumerate(commits, 1):
        short_sha = c["commit_sha"][:7]
        files_str = ", ".join(c.get("files", []))[:60]
        time_str = _time_ago(c.get("committed_at", ""))
        repo = c.get("repo", active_repo)
        lines.append(
            f"{i}. `{short_sha}` — {time_str}\n"
            f"   {c['message']}\n"
            f"   _`{repo}` • {files_str}_"
        )

    active_branch = user.get("active_branch") or user.get("branch", "main")
    await update.message.reply_text(
        "\n\n".join(lines),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(
                f"View on GitHub ↗",
                url=f"https://github.com/{active_repo}/commits/{active_branch}"
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

    active_repo = user.get("active_repo") or user.get("default_repo", "—")
    active_branch = user.get("active_branch") or user.get("branch", "main")
    default_repo = user.get("default_repo", "—")

    auto_note = ""
    if user.get("active_repo") and user.get("active_repo") != default_repo:
        auto_note = f"\n📡 Auto-detected from VS Code"

    await update.message.reply_text(
        f"📊 *GitPhone Status*\n\n"
        f"👤 Registered: ✅\n"
        f"📦 Repo: `{active_repo}`{auto_note}\n"
        f"🌿 Branch: `{active_branch}`\n"
        f"🔗 GitHub: Connected ✅\n\n"
        f"📁 Staged files: {len(staged)} pending\n"
        f"🕐 Last sync: {last_sync}\n"
        f"📝 Total commits via GitPhone: {len(commits)}\n\n"
        f"Use /repo to see repo details, /files to commit.",
        parse_mode=ParseMode.MARKDOWN
    )


# ── /help Command ──────────────────────────────────────────────────────────────

async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = str(update.effective_user.id)
    is_admin = _is_admin(telegram_id)

    user_commands = (
        "🛠 *GitPhone Commands*\n\n"
        "📁 *Staging & Commits*\n"
        "/files   — Select staged files & commit\n"
        "/preview — Preview diffs before committing\n"
        "/unstage — Remove a file from staged list\n"
        "/clear   — Clear all staged files\n\n"
        "📦 *Repo & Branch*\n"
        "/repo    — Show active repo (auto-detected)\n"
        "/branch  — Switch branch\n"
        "/log     — Recent commit history\n"
        "/status  — Connection & repo status\n\n"
        "⚙️ *Account*\n"
        "/auth    — Update GitHub token\n"
        "/start   — Setup or reconfigure\n"
        "/cancel  — Cancel current operation\n"
        "/help    — This message\n\n"
        "💡 *Tip:* Save any file in VS Code — it auto-stages and "
        "the repo is auto-detected from your git remote."
    )

    admin_commands = (
        "\n\n🔐 *Admin Commands*\n"
        "/ban `<id>` `[reason]` — Ban a user\n"
        "/unban `<id>` — Restore a user\n"
        "/users `[page]` — List all users\n"
        "/broadcast `<msg>` — Message all users\n"
        "/stats — Platform statistics\n"
        "/revoke `<id>` — Force user to re-auth"
    )

    await update.message.reply_text(
        user_commands + (admin_commands if is_admin else ""),
        parse_mode=ParseMode.MARKDOWN
    )


# ── Admin Commands ────────────────────────────────────────────────────────────

async def admin_ban_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = str(update.effective_user.id)
    if not _is_admin(telegram_id):
        await update.message.reply_text("⛔ Admin only.")
        return

    args = context.args
    if not args:
        await update.message.reply_text("Usage: `/ban <telegram_id> [reason]`", parse_mode=ParseMode.MARKDOWN)
        return

    target_id = args[0]
    reason = " ".join(args[1:]) if len(args) > 1 else "Banned by admin"

    target = get_user_by_telegram_id(target_id)
    if not target:
        await update.message.reply_text(f"❌ User `{target_id}` not found.", parse_mode=ParseMode.MARKDOWN)
        return

    ok = ban_user(target_id, reason)
    if ok:
        await update.message.reply_text(
            f"✅ User `{target_id}` banned.\nReason: {reason}",
            parse_mode=ParseMode.MARKDOWN
        )
        try:
            await context.bot.send_message(
                chat_id=int(target_id),
                text="⛔ Your GitPhone account has been suspended.\nContact support to appeal."
            )
        except Exception:
            pass
    else:
        await update.message.reply_text(f"❌ Failed to ban `{target_id}`.", parse_mode=ParseMode.MARKDOWN)


async def admin_unban_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = str(update.effective_user.id)
    if not _is_admin(telegram_id):
        await update.message.reply_text("⛔ Admin only.")
        return

    args = context.args
    if not args:
        await update.message.reply_text("Usage: `/unban <telegram_id>`", parse_mode=ParseMode.MARKDOWN)
        return

    target_id = args[0]
    ok = unban_user(target_id)
    if ok:
        await update.message.reply_text(f"✅ User `{target_id}` unbanned.", parse_mode=ParseMode.MARKDOWN)
        try:
            await context.bot.send_message(
                chat_id=int(target_id),
                text="✅ Your GitPhone account has been reinstated. You can use /files again."
            )
        except Exception:
            pass
    else:
        await update.message.reply_text(f"❌ User `{target_id}` not found.", parse_mode=ParseMode.MARKDOWN)


async def admin_users_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = str(update.effective_user.id)
    if not _is_admin(telegram_id):
        await update.message.reply_text("⛔ Admin only.")
        return

    args = context.args
    page = int(args[0]) - 1 if args and args[0].isdigit() else 0
    page_size = 10

    users = get_all_users(limit=page_size, offset=page * page_size)
    if not users:
        await update.message.reply_text("📭 No users found.")
        return

    lines = [f"👥 *Users* (page {page + 1})\n"]
    for u in users:
        repo = u.get("active_repo") or u.get("default_repo", "—")
        status = "⛔" if u.get("status") == "banned" else "✅"
        last = _time_ago(u.get("last_active", ""))
        lines.append(f"{status} `{u['telegram_id']}` — `{repo}` — {last}")

    lines.append(f"\n_Use /users {page + 2} for next page_")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def admin_broadcast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = str(update.effective_user.id)
    if not _is_admin(telegram_id):
        await update.message.reply_text("⛔ Admin only.")
        return

    args = context.args
    if not args:
        await update.message.reply_text("Usage: `/broadcast <message>`", parse_mode=ParseMode.MARKDOWN)
        return

    message = " ".join(args)
    users = get_all_users(limit=1000)

    sent = 0
    failed = 0
    for u in users:
        if u.get("status") == "banned":
            continue
        try:
            await context.bot.send_message(
                chat_id=int(u["telegram_id"]),
                text=f"📢 *GitPhone Announcement*\n\n{message}",
                parse_mode=ParseMode.MARKDOWN
            )
            sent += 1
        except Exception:
            failed += 1

    await update.message.reply_text(
        f"✅ Broadcast sent!\n"
        f"✉️ Delivered: {sent}\n"
        f"❌ Failed: {failed}"
    )


async def admin_stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = str(update.effective_user.id)
    if not _is_admin(telegram_id):
        await update.message.reply_text("⛔ Admin only.")
        return

    stats = count_stats()
    await update.message.reply_text(
        f"📊 *GitPhone Stats*\n\n"
        f"👥 Users: {stats.get('total_users', 0)} registered\n"
        f"⛔ Banned: {stats.get('banned_users', 0)}\n"
        f"📁 Staged: {stats.get('pending_files', 0)} pending files\n"
        f"📝 Commits: {stats.get('total_commits', 0)} total",
        parse_mode=ParseMode.MARKDOWN
    )


async def admin_revoke_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = str(update.effective_user.id)
    if not _is_admin(telegram_id):
        await update.message.reply_text("⛔ Admin only.")
        return

    args = context.args
    if not args:
        await update.message.reply_text("Usage: `/revoke <telegram_id>`", parse_mode=ParseMode.MARKDOWN)
        return

    target_id = args[0]
    ok = revoke_api_key(target_id)
    if ok:
        await update.message.reply_text(
            f"✅ API key revoked for `{target_id}`.\n"
            f"User must re-connect the VS Code extension.",
            parse_mode=ParseMode.MARKDOWN
        )
    else:
        await update.message.reply_text(f"❌ User `{target_id}` not found.", parse_mode=ParseMode.MARKDOWN)


# ── Conversation Handler Builders (exported to main.py) ───────────────────────

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


def build_auth_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("auth", auth_handler)],
        states={
            WAITING_AUTH_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, auth_token_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
        allow_reentry=True,
    )


def build_branch_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("branch", branch_handler)],
        states={
            WAITING_NEW_BRANCH: [MessageHandler(filters.TEXT & ~filters.COMMAND, branch_name_handler)],
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)],
        allow_reentry=True,
    )
