# 11 — MVP Scope

## MVP Definition

```
Current state of GitPhone (fully implemented and demoable).
This is NOT a plan for what to build — it's what already exists.
```

---

## ✅ IN SCOPE (Implemented)

```
Core Features:
  ✅ File watch (onDidSaveTextDocument)
  ✅ Diff computation (diff npm)
  ✅ CRLF → LF normalization
  ✅ Binary file detection + handling
  ✅ Minified file detection + handling
  ✅ 10MB hard limit
  ✅ Git repo auto-detection (.git/config)
  ✅ Branch auto-detection (.git/HEAD)
  ✅ Change type detection (create/modify/delete)
  ✅ File rename detection (delete+create)

Setup:
  ✅ API key generation + SHA-256 auth
  ✅ GitHub Device Flow OAuth (browser-based)
  ✅ GitHub PAT fallback
  ✅ Registration endpoint
  ✅ One-time setup panel (vs CodeWebview)
  ✅ Encrypted API key storage (VS Code secure storage)

Backend API:
  ✅ POST /register
  ✅ POST /sync-file
  ✅ GET /staged-files
  ✅ POST /staged-files (reconciliation)
  ✅ POST /commit-direct
  ✅ DELETE /staged-files (single)
  ✅ POST /staged-files/clear
  ✅ POST /auth/start
  ✅ POST /auth/poll
  ✅ GET /health
  ✅ GET /version

GitHub Integration:
  ✅ Commit via PyGithub
  ✅ SHA conflict check
  ✅ Branch picker (live from GitHub API)
  ✅ Create new branch from default
  ✅ Protected branch detection + new branch creation
  ✅ PR auto-creation (non-default branch)
  ✅ Force commit (overwrite)

Bot Features:
  ✅ /start — welcome + status
  ✅ /auth — Device Flow login
  ✅ /files — inline keyboard toggle
  ✅ /preview — diff preview before commit
  ✅ /unstage — remove file from staged list
  ✅ /clear — clear all staged files
  ✅ /repo — show active repo
  ✅ /branch — switch branch
  ✅ /log — commit history
  ✅ /status — connection status
  ✅ /help — all commands
  ✅ /cancel — abort current flow
  ✅ Admin: /ban, /unban, /users, /broadcast, /stats, /revoke
  ✅ Channel logging (LOG_CHANNEL_ID)
  ✅ Banned user check

Extension Features:
  ✅ Status bar (🟢/⚠️/🔴)
  ✅ Sidebar TreeView (stagedFilesProvider)
  ✅ Manual sync button
  ✅ Health check polling
  ✅ Schema version check
  ✅ Local cache (no API on file save)
  ✅ Encryption (VS Code built-in)
  ✅ Ignore patterns (.git, node_modules, etc.)

Deployment:
  ✅ Docker-based Render deployment
  ✅ Telegram webhook (not polling)
  ✅ Health check endpoint
  ✅ render.yaml config
  ✅ Env var management
```

---

## ❌ OUT OF SCOPE (Not Yet Implemented)

```
  ❌ Scheduling (APScheduler)
  ❌ Multi-repo management in bot
  ❌ AES-256 encryption for stored tokens
  ❌ Keepalive pings
  ❌ Dormancy detection
  ❌ Farewell messages
  ❌ Rate limiting
  ❌ Web fallback UI
  ❌ VS Code Marketplace publish (manual .vsix install)
  ❌ BYOD (single Supabase for all users)
  ❌ Full team/multi-user support
  ❌ E2E tests
  ❌ CI/CD pipeline
  ❌ Custom domain
  ❌ Staleness warnings (72hr)
  ❌ Auto-merge conflicts
  ❌ Commit scheduling
  ❌ Stats/analytics dashboard

All of these are planned post-MVP.
```

---

## MVP Success Criteria

```
1. Developer saves file in VS Code
   → Status bar shows 🟢 GitPhone — 1 file staged

2. Developer opens Telegram
   → /files shows the file as selectable button

3. Developer selects file + types message
   → Commits instantly

4. GitHub refresh shows commit
   → Real commit by developer's account

5. Repeat with branch switching
   → Commit goes to selected branch

6. Admin can manage users
   → Ban/unban/list/broadcast work

Demo time: 90 seconds.
```

---

## What Makes MVP Impressive

```
✅ Real GitHub commits from phone
✅ Genuinely useful day one
✅ Three components connected (VS Code + Telegram + GitHub)
✅ Branch picker + PR creation (unexpected sophistication)
✅ OAuth Device Flow (no token sharing)
✅ Admin system (unexpected completeness)
```
