# 03 — Tech Stack

## Stack Is Locked
Do not suggest alternatives. Every choice below was made
deliberately. See 14_DECISIONS_LOG.md for full reasoning.

---

## Backend

### Python 3.11+
```
Why: Most bot libraries, GitHub libraries,
     and diff libraries are Python-first.
     Entire backend in one language.
```

### FastAPI (latest stable)
```
pip install fastapi uvicorn

Why:
- Fully async, matches bot perfectly
- Auto-generates API docs (/docs)
- Pydantic validation built in
- Most modern Python API framework
- Easy Render deployment
```

### python-telegram-bot v21+
```
pip install python-telegram-bot==21.*

Why:
- Biggest community (26k+ GitHub stars)
- Most tutorials and resources
- Built-in ConversationHandler for multi-step flows
- Clean inline keyboard implementation
- Callback queries are simple
- Webhook support is solid
- v21 is fully async
```

### PyGithub (latest)
```
pip install PyGithub

Why:
- Most mature GitHub API Python wrapper
- File commits in clean few lines
- SHA fetching is simple
- Well documented
```

### diff-match-patch (Google)
```
pip install diff-match-patch

Why:
- Google's own library
- Same algorithm used in Google Docs
- Applies patches to text perfectly
- Battle tested at scale
```

### supabase-py (latest)
```
pip install supabase

Why:
- Official Supabase Python client
- Consistent with JS client API
- Simple table operations
```

### APScheduler — FUTURE
```
pip install apscheduler
Planned for scheduling feature, not yet implemented.
```

---

## Telegram Bot

### python-telegram-bot v21 (same as above)
```
Key features used:
- InlineKeyboardMarkup (file buttons + branch picker)
- CallbackQueryHandler (toggle files, pick branch)
- MessageHandler (commit messages, branch names)
- CommandHandler (/files, /log, /auth, /branch etc.)
- ConversationHandler (multi-step flows)
- Webhook mode (not polling)
- Application builder pattern
```

---

## Database

### Supabase (ONE central)
```
pip install supabase (backend)
No JS client needed — extension uses axios to REST API

Why:
- Free tier generous (500MB)
- Simple REST API via Python client
- SQL editor in dashboard
- Easy to set up (5 minutes)

MVP: ONE central Supabase (yours)
All users isolated by telegram_id
BYOD = FUTURE (each dev owns their own DB)
```

---

## Hosting

### Render (Docker-based)
```
Why Render over others:
- Free tier: YES
- No credit card: YES
- Docker support: YES (actual deployment uses Dockerfile)
- Does not sleep in webhook mode: YES
- FastAPI support: excellent
- Deploy from GitHub: YES
- Environment variables: YES
- Health checks: YES

Actual deployment: Docker-based (not bare Python)
  See backend/Dockerfile and backend/render.yaml
```

---

## VS Code Extension

### TypeScript (strict mode)
```
Why: Standard language for VS Code extensions.
```

### VS Code Extension API (vscode npm)
```
Key APIs used:
- vscode.workspace.onDidSaveTextDocument (file watcher)
- vscode.workspace.onDidCreateFiles (new files)
- vscode.workspace.onDidDeleteFiles (deletions)
- vscode.workspace.onDidRenameFiles (renames)
- vscode.window.createStatusBarItem (status bar)
- vscode.window.createWebviewPanel (setup panel)
- vscode.ExtensionContext.globalState (config + cache)
- vscode.workspace.workspaceFolders (repo root)
- vscode.extensions.getExtension('vscode.git') (sidebar)
```

### diff (npm library)
```
npm install diff
npm install @types/diff

Why:
- 6M+ weekly downloads
- Most popular JS diff library
- Creates unified diff format
- Works perfectly with diff-match-patch
- Lightweight, no dependencies
```

### axios
```
npm install axios

Why:
- HTTP client for calling Render backend
- Promise-based, async/await friendly
- Better than fetch for error handling
- TypeScript types included
```

---

## Full requirements.txt (Backend)

```
fastapi
uvicorn[standard]
python-telegram-bot==21.*
PyGithub
diff-match-patch
supabase
python-dotenv
pydantic
httpx
```

---

## Full package.json Dependencies (Extension)

```json
{
  "dependencies": {
    "axios": "^1.6.0",
    "diff": "^5.1.0"
  },
  "devDependencies": {
    "@types/vscode": "^1.85.0",
    "@types/diff": "^5.0.9",
    "@types/node": "^20.0.0",
    "typescript": "^5.3.0",
    "esbuild": "^0.19.0",
    "@vscode/vsce": "^2.22.0"
  }
}
```

---

## Version Pinning Rules

```
Always pin major versions in requirements.txt
python-telegram-bot==21.* (major pinned)
Use latest stable for everything else
```
