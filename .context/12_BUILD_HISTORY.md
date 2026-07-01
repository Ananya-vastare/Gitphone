# 12 — Build History

## Purpose

```
This file logs the development history of GitPhone.
It replaces the original 12_HACKATHON_PLAN.md which described
a future 48-hour build sprint that is no longer relevant.

The project was built over multiple iterations and is now
functional as an MVP. This file tracks major milestones
for transparency and future reference.
```

---

## Milestones

```
Phase 1 — Foundation
  [x] Supabase schema designed + deployed
  [x] FastAPI backend scaffolded
  [x] User registration endpoint
  [x] GitHub commit via PyGithub
  [x] SHA conflict detection
  [x] Branch picker + protected branch handling
  [x] PR auto-creation

Phase 2 — Bot Features
  [x] Bot setup with webhook mode
  [x] Telegram ID authorization check
  [x] /files with inline keyboard
  [x] File toggle callbacks
  [x] Commit message flow
  [x] Review + confirm screen
  [x] Branch selection in commit flow
  [x] Force commit option
  [x] /log, /status, /repo, /branch
  [x] /preview, /unstage, /clear
  [x] OAuth Device Flow via /auth
  [x] Admin commands (/ban, /unban, /users, etc.)
  [x] Channel logging

Phase 3 — VS Code Extension
  [x] Setup panel (webview)
  [x] API key authentication
  [x] File watcher (onDidSaveTextDocument)
  [x] CRLF normalization
  [x] Binary + minified detection
  [x] 10MB limit enforcement
  [x] Local cache
  [x] Diff computation (diff npm)
  [x] Status bar
  [x] Sidebar TreeView (stagedFilesProvider)
  [x] Manual sync button
  [x] Schema version checker
  [x] Health check polling
  [x] Auto git detection from .git/config

Phase 4 — Deployment
  [x] Dockerfile written
  [x] render.yaml configured
  [x] Webhook mode for Telegram
  [x] Environment variable management
  [x] Health check endpoint
```

---

## Changelog Format (FUTURE)

```
v0.1.0 — MVP
  - Initial release
  - Basic file sync
  - Telegram bot commit
  - Branch picker
  - OAuth Device Flow

v0.2.0 — Future
  - Scheduling
  - AES-256 encryption
  - Keepalive system

See CHANGELOG.md in public/ for full version history.
```
