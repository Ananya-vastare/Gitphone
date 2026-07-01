# 06 — Bot Flows

## Overview

```
Bot library: python-telegram-bot v21 (async)
Mode:        WEBHOOK (not polling)
State:       Managed via ConversationHandler
             or user_data dict per session

Every handler checks authorization first (via _check_registered).
Unregistered users get /start prompt.
Banned users get "[Banned]" message.
Bot runs inside the same Render Docker service as FastAPI.
```

---

## Command List (Current — All Implemented)

```
/start     → Welcome or show status for returning users
/auth      → GitHub Device Flow login (browser-based)
/files     → Select files grouped by repo & commit
/log       → Recent commit history (last 10)
/status    → Connection status + active repo info
/repo      → Show active repo (auto-detected from VS Code)
/branch    → Switch active branch
/preview   → Preview diffs before committing
/unstage   → Remove a specific file from staged list
/clear     → Clear all staged files
/cancel    → Cancel current operation
/help      → Show all commands

Admin Commands (ADMIN_TELEGRAM_IDS env var):
/ban <id> [reason]  - Ban a user
/unban <id>         - Unban a user
/users [page]       - List all users (paginated)
/broadcast <msg>    - Message all users
/stats              - Global platform stats
/revoke <id>        - Force user to re-authenticate
```

---

## Conversation States

```python
SELECTING_FILES          = 10   # /files, user toggling file buttons
WAITING_MESSAGE          = 11   # user typing commit message
CONFIRM_COMMIT           = 12   # review screen shown
SELECTING_BRANCH         = 13   # branch picker after commit message
WAITING_NEW_BR_NAME      = 14   # typing new branch name
WAITING_PROTECTED_BRANCH_NAME = 15  # typing branch after protection error
WAITING_NEW_BRANCH       = 20   # /branch, awaiting branch name
```

---

## /start Flow

```
NEW USER (not in users table or no github_token):
  Bot: 👋 Welcome to GitPhone!
       Commit to GitHub from anywhere.
       Use /auth to sign in with GitHub →
       (returns ConversationHandler.END immediately)

RETURNING USER (registered + has token):
  Bot: 👋 Welcome back!
       📦 user/repo • main
       🕐 Last active: 2h ago
       📁 3 file(s) staged
       Use /files to commit, or /help for all commands.
```

---

## /auth Flow (GitHub Device Flow)

```
1. User sends /auth
2. Bot contacts GitHub for device code
3. Bot replies:
   [Admin] Sign in with GitHub
   1️⃣ Open link: https://github.com/login/device
   2️⃣ Enter code: XXXX-XXXX
   3️⃣ Click Authorize
   (Waiting for authorization...)
4. Bot starts background async polling task
5. When user authorizes in browser:
   Bot: ✅ GitHub connected! Signed in as username.
        Now set your repository with /repo owner/repo-name
6. If timeout (15 min): "Authorization expired. Use /auth."
7. If cancelled: User sends /cancel
```

---

## /files Flow (Core Feature)

```
STEP 1: User types /files
───────────────────────────

Bot fetches pending files grouped by repo.

IF no files staged:
  Bot: 📭 No files staged yet.
       Save a file in VS Code to stage it.
       Active: user/repo • main

IF files exist:
  ┌────────────────────────────────────┐
  │ [Files] user/repo • main           │
  │                                    │
  │ ☐  ✏ src/index.js          1.2KB  │
  │ ☐  ✏ src/auth.js           3.4KB  │
  │ ☐  ➕ README.md             0.8KB  │
  │                                    │
  │ [☑ Select All]  [✅ Done]          │
  └────────────────────────────────────┘

  If multiple repos, files grouped with repo header.

STEP 2: User taps files to toggle
  Each tap → callback query → message edited in place
  Checkmark toggles ✅/☐

STEP 3: User taps Done
  IF no files selected: "⚠️ No files selected."
  IF files selected: "✏️ Type your commit message:"
     shows selected files list

STEP 4: User types commit message
  Bot stores message, shows BRANCH PICKER:
  ┌────────────────────────────────────┐
  │ [Branch] Choose branch to commit:  │
  │                                    │
  │ [OK] main (current)                │
  │ [Branch] develop (default)         │
  │ [Branch] feature/login             │
  │ [Branch] fix/auth                  │
  │ ➕ Create new branch...            │
  │ [X] Cancel                         │
  └────────────────────────────────────┘

  Branches fetched LIVE from GitHub API.

STEP 5: User picks existing branch
  Review screen:
  ┌────────────────────────────────────┐
  │ 📦 Review Commit                   │
  │                                    │
  │ Files: • src/index.js              │
  │        • README.md                 │
  │                                    │
  │ 💬 fix: updated auth logic         │
  │ 🌿 feature-branch • user/repo      │
  │                                    │
  │ [🚀 Commit Now] [❌ Cancel]        │
  └────────────────────────────────────┘

STEP 6A: Commit Now (no conflict)
  Bot: ⏳ Committing...
  [Backend runs SHA check, applies diff, commits]
  Bot: ✅ Committed!
       🔗 abc123f
       💬 fix: updated auth logic
       🌿 feature-branch • user/repo
       🔀 PR #42 created → ready to merge
         (if non-default branch)
       Or: [View Commit on GitHub ↗]

STEP 6B: Conflict detected
  Bot: ⚠️ Conflict Detected
       Files: • src/index.js
       [🔄 Force Commit (overwrite)] [❌ Cancel]

STEP 6C: Branch protected
  Bot: 🔒 Branch main is protected.
       Type a new branch name to commit to instead:
       (e.g. patch-1 or fix/auth)
  → Creates new branch from default, commits to it
  → Auto-creates PR

STEP 6D: User chose "Create new branch"
  Bot: Type branch name (e.g. feature/my-fix):
  → Creates branch from default branch
  → Shows review screen → Commit → Auto PR
```

---

## /log Flow

```
User: /log
Bot: 📜 Recent Commits (user/repo)
     1. abc123f — just now
        fix: updated auth logic
        user/repo • src/index.js, README.md
     2. def456a — 2h ago
        feat: added user model
        user/repo • src/models/user.js
     [View on GitHub ↗]
```

---

## /status Flow

```
User: /status
Bot: 📊 GitPhone Status
     👤 Registered: ✅
     📦 Repo: user/repo (Auto-detected from VS Code)
     🌿 Branch: main
     🔗 GitHub: Connected ✅
     📁 Staged files: 3 pending
     🕐 Last sync: 5 minutes ago
     📝 Total commits: 47
```

---

## /repo Flow

```
Without args: Shows current active repo info
  📦 user/repo • main
  Auto-detected from VS Code
  Use /branch to switch branch.

With args: /repo owner/repo-name
  Bot validates repo access via GitHub API
  Sets as default + active repo
  Returns default branch name
```

---

## /branch Flow

```
Without args:
  Bot: Current: main
       Type the branch name to switch:

With args: /branch new-branch-name
  Bot: ✅ Branch switched to new-branch-name
       Future commits will go to new-branch-name.
```

---

## /preview Flow

```
Shows diff snippets for first 5 staged files
Bot: 👁 Diff Preview - 3 file(s) staged
     `src/index.js` (1.2KB)
     ```diff
     @@ -10,7 +10,7 @@
      function authenticate() {
     -  return null;
     +  return checkToken();
      }
     ```
```

---

## /unstage Flow

```
Without args: Lists staged files with usage hint
With args: /unstage src/filename.py
  Bot: ✅ Unstaged: src/filename.py
       Will be re-staged next time you save it.
```

---

## /clear Flow

```
Bot: ⚠️ Clear All Staged Files?
     This will remove all 3 staged file(s).
     [Clear] [Cancel]
On confirm: ✅ Cleared X staged file(s).
```

---

## /help Flow

```
User: /help
Bot: 🛠 GitPhone Commands
     /files   - Select staged files & commit
     /preview - Preview diffs
     /unstage - Remove file from staged list
     /clear   - Clear all staged files
     /repo    - Show active repo
     /branch  - Switch branch
     /log     - Recent commit history
     /status  - Connection & repo status
     /auth    - Update GitHub token
     /start   - Setup or reconfigure
     /cancel  - Cancel current operation
     /help    - This message
```

---

## State Management

```python
context.user_data stores per-session:
  selected_files: set[str]         # file IDs toggled
  staged_data: dict                # {file_id: file_row, ...}
  commit_message: str              # typed by user
  commit_branch: str               # branch selected in picker
  staged_rows_for_force: list      # rows cached for force commit
  file_ids_for_force: list         # IDs cached for force commit

State is cleared on:
  → Successful commit (context cleared)
  → /cancel command
  → Any error that aborts the flow
```

---

## Callback Query Names

```
FILE_TOGGLE:{file_id}              → Toggle file on/off
FILE_SELECT_ALL                    → Select all files
FILE_DONE                          → Done selecting
BRANCH_PICK:{branch_name}          → Pick existing branch
BRANCH_NEW                         → Create new branch
COMMIT_NOW                         → Confirm commit
COMMIT_FORCE                       → Force commit (overwrite)
COMMIT_CANCEL                      → Cancel commit
CLEAR_CONFIRM                      → Confirm clear all
```

---

## FUTURE Bot Flows (Not Yet Implemented)

```
/schedule     — Schedule a commit for later
/pending      — View/cancel scheduled commits
Web fallback  — Mobile web UI if Telegram is down
Multi-repo UI — Full multi-repo management
```
