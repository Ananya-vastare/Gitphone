# GitPhone — AI Context Index
> Read this file first before reading any other context file.
> This is the master index for all AI agents working on this project.

---

## What Is GitPhone

GitPhone is a developer tool that enables real GitHub commits directly
from a Telegram bot controlled from a phone, with a VS Code extension
as the local bridge. Developers stage changes in VS Code, then commit
from anywhere using Telegram — no laptop needed.

---

## Current Status

```
Phase:        MVP COMPLETE (features built, deployed on Render)
Mode:         Maintenance / Future feature development
Stack:        Locked — no architecture changes without updating this file
Last updated: See git log
```

---

## How To Use These Context Files

Every AI agent working on this project MUST:

1. Read this file (00_README.md) first
2. Read the file relevant to your task (see map below)
3. Note: Some features described in context files may be marked **[FUTURE]**
   — these are planned but NOT yet implemented. Do NOT build them unless
   explicitly asked.
4. If you add new features, update the relevant context file afterward

---

## File Map — Read This For That Task

| Task | Read These Files |
|---|---|
| Understanding the product | 01_PRODUCT.md |
| System design / architecture | 02_ARCHITECTURE.md |
| Choosing libraries / versions | 03_TECH_STACK.md |
| Database schema / SQL | 04_DATABASE.md |
| Security implementation | 05_SECURITY.md |
| Telegram bot UX / commands | 06_BOT_FLOWS.md |
| VS Code extension features | 07_EXTENSION.md |
| FastAPI routes / backend | 08_BACKEND.md |
| Diff / file sync logic | 09_DIFF_STRATEGY.md |
| Deployment to Render | 10_DEPLOYMENT.md |
| What is in MVP scope | 11_MVP_SCOPE.md |
| Build history | 12_BUILD_HISTORY.md |
| Post MVP roadmap | 13_OPEN_SOURCE_ROADMAP.md |
| Why decisions were made | 14_DECISIONS_LOG.md |
| Demo script | 15_DEMO_SCRIPT.md |

---

## Golden Rules For All AI Agents

```
RULE 1:  Stack is locked. Do not suggest alternatives.
RULE 2:  Read the relevant context file before writing code.
RULE 3:  ONE central Supabase (BYOD is FUTURE).
RULE 4:  No AES-256 encryption (FUTURE).
RULE 5:  No APScheduler / scheduling (FUTURE).
RULE 6:  Render for hosting (Docker-based, not bare Python).
RULE 7:  python-telegram-bot v21 (not aiogram).
RULE 8:  Webhook mode for bot (not polling).
RULE 9:  Diffs preferred but full content also accepted.
RULE 10: 10MB hard limit on all files.
RULE 11: Auth is API-key based (SHA-256 hash) + Telegram device flow.
RULE 12: Git repo auto-detected from .git/config - not configured manually.
```

---

## Three Components At A Glance

```
1. VS Code Extension (TypeScript) — PRIVATE
   Runs on developer machine
   Watches files, computes diffs, syncs to backend
   Sidebar shows staged/working changes from vscode.git API

2. Backend (Python/FastAPI + Bot) — PRIVATE
   Runs on Render (free, Docker, no credit card)
   FastAPI + python-telegram-bot in one service
   ONE central Supabase (user isolation by telegram_id)

3. Public Repo (Docs + Schema) — PUBLIC
   schema.sql for developers to run
   Setup guide, docs, changelog
```

---

## Repo Structure

```
gitphone/
├── .context/          ← YOU ARE HERE (AI context files)
├── backend/           ← FastAPI + Telegram bot (private)
├── extension/         ← VS Code extension (private)
├── public/            ← Public docs + schema (public)
```

---

## Quick Glossary

```
Supabase (central) = Only DB used. All users isolated by telegram_id
BYOD              = Bring Your Own Database (FUTURE feature)
base_sha          = Git SHA of file version diff was made against
staged file       = File diff synced to cloud, not yet committed
API key           = SHA-256 hashed key, generated at registration
Device Flow       = GitHub OAuth device code flow (no PAT needed)
Render            = Hosting platform (free tier, Docker-based)
```
