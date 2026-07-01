# 02 — Architecture

## Full System Diagram (Current)

```
┌──────────────────────────────────────────────────┐
│              DEVELOPER'S MACHINE                 │
│                                                   │
│   VS Code Extension (TypeScript)                  │
│   ┌────────────────────────────────────────┐      │
│   │ Setup Panel  → OAuth or PAT config     │      │
│   │ File Watcher → onDidSaveTextDocument   │      │
│   │ Diff Engine  → computes local diffs    │      │
│   │ Local Cache  → avoids GitHub API spam  │      │
│   │ Sidebar View → git staged/working      │      │
│   │ Status Bar   → `$(check) GitPhone 3S` │      │
│   │ Git Detection→ reads .git/config+HEAD │      │
│   └────────────────────────────────────────┘      │
└───────────────────────┬──────────────────────────┘
                        │
                        │ HTTPS POST /sync-file
                        │ {telegram_id, filepath,
                        │  diff, base_sha, is_binary,
                        │  active_repo, active_branch,
                        │  change_type}
                        ▼
┌──────────────────────────────────────────────────┐
│           RENDER SERVER (Docker, always on)       │
│                                                   │
│  ┌─────────────────┐   ┌──────────────────────┐  │
│  │   FastAPI        │   │  Telegram Bot        │  │
│  │                  │   │  (python-telegram-   │  │
│  │  POST /register  │   │   bot v21)           │  │
│  │  POST /sync-file │   │                      │  │
│  │  GET  /staged... │   │  /start   /auth      │  │
│  │  POST /commit... │   │  /files   /log       │  │
│  │  POST /unstage   │   │  /status  /repo      │  │
│  │  GET  /version   │   │  /branch  /preview   │  │
│  │  GET  /health    │   │  /unstage /clear     │  │
│  │  POST /auth/dev… │   │  /help    /cancel    │  │
│  │                  │   │  /ban /unban /users  │  │
│  │                  │   │  /broadcast /stats   │  │
│  │                  │   │  /revoke (admin)     │  │
│  └────────┬─────────┘   └──────────┬───────────┘  │
│           └──────────┬─────────────┘              │
│                      │                            │
│         ┌────────────▼─────────────┐              │
│         │   Service Layer          │              │
│         │   github_service.py      │              │
│         │   diff_service.py        │              │
│         │   supabase_service.py    │              │
│         │   auth.py (API key)      │              │
│         │   channel_logger.py      │              │
│         │   admin.py               │              │
│         └────────────┬─────────────┘              │
└──────────────────────┼───────────────────────────┘
                       │
           ┌───────────┴───────────┐
           │                       │
           ▼                       ▼
┌──────────────────┐    ┌───────────────────────┐
│    SUPABASE       │    │      GITHUB API       │
│   (ONE central)   │    │  (via PyGithub)       │
│                   │    │                       │
│  users            │    │  Fine-grained PAT     │
│  staged_files     │    │  or OAuth token       │
│  commit_log       │    │  Contents API:        │
│                   │    │  create/update/delete │
│  All users        │    │  Branch mgmt          │
│  isolated by      │    │  PR creation          │
│  telegram_id      │    └───────────────────────┘
└──────────────────┘
```

---

## Data Flow — File Staging

```
1. Developer saves src/index.js in VS Code

2. Extension file watcher fires

3. Extension reads file from disk

4. Extension reads cached version
   (last known committed state)

5. Extension computes diff between
   cached and current using diff npm

6. Extension checks:
   - Is file binary? (store full)
   - Is file over 10MB? (reject)
   - Normalize CRLF to LF
   - Detect git repo from .git/config + HEAD

7. Extension POST to Render:
   /sync-file
   {
     telegram_id: "123456789",
     filepath: "src/index.js",
     diff: "unified diff text...",
     base_sha: "abc123def",
     is_binary: false,
     file_size: 240,
     active_repo: "user/repo",
     active_branch: "main",
     change_type: "modify"
   }

8. Render receives, validates API key,
   stores diff in Supabase staged_files

9. Status bar updates:
   $(check) GitPhone — 1 staged
```

---

## Data Flow — Commit From Phone

```
1. Developer opens Telegram, types /files

2. Bot checks user is registered + not banned

3. Bot fetches pending files grouped by repo

4. Bot renders inline keyboard:
   one button per file, grouped by repo

5. Developer taps files to toggle selection

6. Developer taps Done Selecting

7. Bot asks for commit message

8. Developer types message

9. Bot shows branch picker:
   - Current branch (default)
   - All existing branches from GitHub
   - "Create new branch" option

10. Developer picks branch

11. Review screen with buttons:
    [🚀 Commit Now] [❌ Cancel]

12. Developer taps Commit Now

13. Backend:
    a. Fetches current file SHA from GitHub
    b. Compares with stored base_sha
    c. If match: apply diff via diff-match-patch
    d. If mismatch: warn user → Force Commit
    e. If branch protected: prompt new branch name
    f. Send to GitHub API
    g. Real commit created ✅
    h. If non-default branch: auto-create PR

14. Bot confirms:
    ✅ Committed! abc123f
    💬 "fix: updated auth logic"
    🌿 feature-branch • user/repo
    If PR: 🔀 PR #42 created → ready to merge

15. staged_files status → committed
    commit_log entry created
```

---

## Component Responsibilities

```
VS Code Extension:
  ✅ Detect file save/create/delete/rename
  ✅ Compute diffs locally (diff npm)
  ✅ Auto-detect git repo + branch
  ✅ Enforce 10MB limit
  ✅ Normalize line endings (CRLF→LF)
  ✅ Detect binary + minified files
  ✅ Cache last committed state
  ✅ Sidebar with staged/working changes
  ✅ Status bar with staged count
  ✅ Setup panel (OAuth + PAT fallback)
  ✅ Sync state reconciliation with backend
  ❌ Does NOT commit
  ❌ Does NOT talk to GitHub

Render Backend:
  ✅ Store user configurations (central Supabase)
  ✅ Store staged file diffs
  ✅ Handle Telegram bot logic
  ✅ Talk to GitHub API (PyGithub)
  ✅ Apply diffs via diff-match-patch
  ✅ Detect conflicts (SHA check)
  ✅ Force commit on conflict
  ✅ Branch management (list, create, pick)
  ✅ Auto-create PR for non-default branches
  ✅ Protected branch detection
  ✅ Admin commands (ban, unban, stats, broadcast)
  ✅ Record commit history
  ✅ Auth via API keys (SHA-256)
  ✅ Channel logging for audit

Supabase (ONE central for all users):
  ✅ Store user configs
  ✅ Store staged diffs
  ✅ Store commit history
  ✅ All isolated by telegram_id
```

---

## Environment Variables (Actual)

```
TELEGRAM_BOT_TOKEN=          # From BotFather
YOUR_SUPABASE_URL=           # Your Supabase project URL
YOUR_SUPABASE_KEY=           # Your Supabase service role key
WEBHOOK_URL=                 # https://your-app.onrender.com
ADMIN_TELEGRAM_IDS=          # Comma-separated admin IDs
LOG_CHANNEL_ID=              # Private Telegram channel ID for logs
GITHUB_CLIENT_ID=            # GitHub OAuth App client ID
GITHUB_CLIENT_SECRET=        # GitHub OAuth App client secret
PORT=8000
```
