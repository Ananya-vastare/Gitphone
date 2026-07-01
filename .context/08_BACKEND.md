# 08 — Backend

## Overview

```
Framework: FastAPI (async)
Port:      8000 (internal, mapped to :80 by Docker)
Entry:     main.py
Mode:      Webhook (Telegram bot)
Deploy:    Render (Docker)
```

---

## File Map

```
backend/
├── main.py                 ← FastAPI app entry, webhook setup, startup/shutdown
├── bot.py                  ← Telegram bot handlers, ConversationHandler, all flows
├── auth.py                 ← API key auth middleware (SHA-256)
├── github_service.py       ← PyGithub wrapper (commits, branch listing, PR creation)
├── supabase_service.py     ← All Supabase DB operations (30+ functions)
├── diff_service.py         ← diff-match-patch apply + conflict detection
├── channel_logger.py       ← Admin logging channel bot
├── admin.py                ← Admin commands handler (/ban, /unban, /users, etc.)
├── routes/
│   ├── register.py         ← POST /register (creates user, returns API key)
│   ├── sync.py             ← POST /sync-file (saves diff to Supabase)
│   ├── staged_files.py     ← GET/POST /staged-files (reconciliation, commit, clear)
│   ├── auth.py             ← POST /auth/start, POST /auth/poll (Device Flow)
│   └── version.py          ← GET /version (schema + version info)
├── models/                 ← Pydantic models (data classes, no ORM)
│   ├── user.py             ← UserCreate, UserResponse
│   ├── commit.py           ← CommitRequest, CommitResponse
│   └── schedule.py         ← FUTURE
├── render.yaml             ← Render deployment config (Docker-based)
├── Dockerfile              ← Docker build definition
├── requirements.txt        ← Python deps
└── .env.example            ← Env var template
```

---

## All Routes

```
PUBLIC (no auth):
  GET  /health               ← { status: "ok" }
  GET  /version              ← { version, schema_version, min_schema_version }
  POST /webhook              ← Telegram bot webhook
  POST /register             ← Returns { api_key, telegram_id }

AUTHENTICATED (X-Api-Key + X-Telegram-Id required):
  POST /sync-file            ← Save staged file diff
  GET  /staged-files         ← Get all pending files
  POST /staged-files          ← Sync state reconciliation
  POST /commit-direct        ← Direct commit (no file selection)
  DELETE /staged-files       ← Clear one file by ID
  POST /staged-files/clear   ← Clear all pending files
  POST /auth/start           ← Start GitHub Device Flow
  POST /auth/poll            ← Poll Device Flow status
```

---

## Request/Response Formats

### POST /register
```json
{
  "telegram_id": "123456789",
  "github_token": "ghp_...",
  "working_dir": "path/to/repo"
}
→ {
  "status": "ok",
  "api_key": "generated-256-bit-key",
  "message": "Welcome to GitPhone!"
}
```

### POST /sync-file
```json
{
  "filepath": "src/index.js",
  "diff": "@@ -10,7 +10,7 @@\n...",
  "full_content": null,
  "base_sha": "abc123def456...",
  "repo": "user/repo",
  "branch": "main",
  "is_binary": false,
  "file_size": 1234,
  "change_type": "modify"
}
→ { "id": "uuid", "status": "pending" }
```

### POST /commit-direct
```json
{
  "file_ids": ["uuid1", "uuid2"],
  "message": "fix: updated auth",
  "branch": "main",
  "force": false
}
→ {
  "status": "ok",
  "commit_sha": "abc123def456",
  "commit_url": "https://github.com/user/repo/commit/abc123..."
}
```

---

## Key Services

### auth.py (API Key Middleware)
```
_auth_exempt: set of paths not requiring auth
  /health, /version, /webhook, /register, /docs, /openapi.json

For authenticated routes:
  1. Extract X-Api-Key + X-Telegram-Id headers
  2. Fetch user by telegram_id
  3. SHA-256 hash incoming key, compare to stored api_key_hash
  4. Reject if mismatch or user not found
  5. Return user row for use in handler
```

### github_service.py
```
Key functions:
  get_repo(repo_name: str) → Repository
  get_branches(repo_name: str) → list[Branch]
  get_default_branch(repo_name: str) → str
  get_file_sha(repo_name, filepath, branch) → str | None
  get_sha_for_tree(repo_name, branch) → str
  create_new_branch(repo_name, new_branch_name) → Branch
  commit_files(repo_name, branch, message, files_to_commit) → Commit
  handle_protected_branch(repo_name, message, files) → creates branch + PR
  create_pr(repo_name, branch, title) → PR
  validate_token() → bool
```

### supabase_service.py
```
Key functions (~30+):
  create_user, get_user, get_user_by_telegram_id
  update_last_active, update_github_token
  update_active_repo, update_active_branch
  update_device_flow_state
  create_staged_file, get_staged_files, get_staged_files_by_ids
  update_staged_file_status, delete_staged_file
  sync_pending_state
  create_commit_log, get_commit_logs, get_commit_count
  get_all_users, get_user_count, get_total_commit_count
  get_stats
```

### diff_service.py
```
Key functions:
  apply_diff(original_content, diff_text) → merged_content
  detect_conflict(original_content, modified_content) → bool
  resolve_conflict_with_merge(original_content, modified_content, diff_text) → merged
```

### bot.py (line counts approximate)
```
Main bot application setup (~200 lines)
  - Application.builder() with webhook
  - ConversationHandler registration (~20 states)
  - /start handler
  - /auth -> Device Flow (auth_handler, _poll_device_auth) (~80 lines)
  - /files handler (~30 lines)
  - FILE_TOGGLE callbacks (~40 lines)
  - select_all_done handler (~15 lines)
  - commit_message_handler (~10 lines)
  - branch_pick_callback (~30 lines)
  - Branch picker flow, SELECTING_BRANCH state (~100 lines)
  - WAITING_NEW_BR_NAME / WAITING_PROTECTED_BRANCH_NAME (~60 lines)
  - CONFIRM_COMMIT review screen (~40 lines)
  - confirm_commit_now / confirm_commit_force (~50 lines)
  - /branch, /repo, /status, /log handlers
  - /preview, /unstage, /clear handlers
  - Admin commands: /ban, /unban, /users, /broadcast, /stats, /revoke
  - Error handling, banned user check
  - Webhook setup at startup
```

### channel_logger.py
```
Sends log messages to a channel specified by LOG_CHANNEL_ID env var.
Functions:
  send_log(message, level="info")
  send_error(message)
  send_user_action(action, telegram_id, details)
```

### admin.py
```
Handlers for admin-only commands. Registered only if ADMIN_TELEGRAM_IDS
is set (comma-separated list of telegram IDs).
```

---

## Environment Variables

```
# Required
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
TELEGRAM_BOT_TOKEN=

# GitHub OAuth Device Flow
GITHUB_CLIENT_ID=
GITHUB_CLIENT_SECRET=
GITHUB_APP_NAME=GitPhone

# Admin
ADMIN_TELEGRAM_IDS=       # Comma-separated (123,456)
LOG_CHANNEL_ID=           # Optional, for channel logging

# Optional
PORT=8000                 # Default 8000
WEBHOOK_URL=              # Render-external URL for Telegram
WEBHOOK_SECRET=           # FUTURE: Telegram webhook secret token

# FUTURE:
# ENCRYPTION_KEY=
# DATABASE_URL=
```

---

## Startup Sequence

```
1. Load env vars (python-dotenv)
2. Init Supabase client
3. Init GitHub service (if GITHUB_CLIENT_ID/TOKEN)
4. Init bot Application
5. Add all handlers (ConversationHandler + commands)
6. Register webhook with Telegram
7. Start uvicorn server
8. On shutdown: bot.stop(), clean up
```

---

## Error Handling

```
All routes wrapped in try/except:
  auth errors       → 401 { "detail": "Invalid API key" }
  not_found         → 404 { "detail": "User not found" }
  supabase_errors   → 502 { "detail": "DB error: ..." }
  github_errors     → 502 { "detail": "GitHub error: ..." }
  validation_errors → 422 from Pydantic

Bot handlers:
  Errors caught in main handler wrapper
  User gets: "⚠️ Something went wrong. Try /files again."
  Error details logged to channel_logger (if configured)
```

---

## FUTURE Backend Features

```
- Scheduled commits (APScheduler)
- Keepalive pings for inactive users
- AES-256 encryption service
- Rate limiting
- Web fallback UI
- Multi-repo management in bot
```
