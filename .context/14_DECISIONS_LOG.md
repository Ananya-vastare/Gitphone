# 14 — Decisions Log

## Architecture Decisions

### Single Supabase (not BYOD)

```
Decision: ONE central Supabase for all users (MVP)
Original plan: Each user brings their own Supabase (BYOD)

Why:
  BYOD adds 6+ hours of implementation time
  Demo doesn't need it
  All users isolated by telegram_id with same effect
  Can migrate to BYOD later without breaking API

Trade-off:
  All eggs in one Supabase basket
  But: fine for MVP, migration path clear
```

### Docker-based Render Deploy (not bare Python)

```
Decision: Docker container on Render
Alternatives considered: Koyeb (needs credit card),
                         Vercel (serverless, unsuitable),
                         Hugging Face Spaces,
                         Deta Space

Why Render Docker:
  No credit card required
  Full Dockerfile control
  uvicorn runs as persistent process
  Perfect for webhook-based bot (no sleep)
  Simple render.yaml config

Why not Koyeb:
  Requires credit card verification
```

### API Key Auth (SHA-256, not JWT)

```
Decision: Per-user API key, SHA-256 hashed, sent as header
Alternatives considered: JWT tokens, session cookies

Why SHA-256:
  Simpler than JWT (no token refresh needed)
  No session management
  Stateless — just hash + compare
  Key generated once, stored hashed, returned plain to client
  Client stores in VS Code secure storage

Trade-off:
  No token expiry (but: user can disconnect/regenerate)
  Revocation: status='banned' in DB
```

### GitHub Device Flow OAuth (not just PAT)

```
Decision: Support both Device Flow + PAT
Alternatives considered: Web OAuth redirect, PAT only

Why Device Flow:
  No token sharing — user logs in via browser
  No PAT needed — simpler onboarding
  Works with any GitHub account
  Bot handles the polling securely

Why PAT fallback:
  Some users prefer explicit PAT control
  Works without browser
```

### python-telegram-bot (not aiogram)

```
Decision: python-telegram-bot v21
Alternatives considered: aiogram, pyTelegramBotAPI

Why:
  Largest community (26k stars)
  Most tutorials and docs
  Built-in ConversationHandler
  Clean webhook support
  Async-native from v21
```

### Diff Strategy: diff npm + diff-match-patch

```
Decision: diff (npm) on client, diff-match-patch on server
Alternatives considered: diff-match-patch everywhere, Git CLI

Why diff npm:
  Most popular JS diff library (6M weekly downloads)
  Produces unified diff format
  Works perfectly with diff-match-patch

Why diff-match-patch:
  Google's library
  Same algorithm as Google Docs
  Battle tested at scale
  Applies patches cleanly

Why not Git CLI:
  Slower, heavier dependency
  Not available in VS Code extension
```

### Manual Sync = full content, Auto = diff

```
Decision: Two modes of sync
  Auto-save (watcher): unified diff
  Manual sync (sidebar button): full base64 content

Why:
  Auto-save needs speed + storage efficiency
  Manual sync is for recovery/reset when local cache is missing
  Backend handles both transparently
```

### Branch Picker on Commit (not just main)

```
Decision: Show branch picker after commit message
Alternatives considered: Comply to /branch before commit

Why:
  User may want different branch per commit
  Picker shows branches LIVE from GitHub API
  Can create new branches on the fly
  Protected branch detection auto-creates new branch + PR

This was initially marked as FUTURE but is fully implemented.
```

### Single Bot File (bot.py) not separated

```
Decision: All bot handlers in one file (bot.py)
Alternatives considered: Split by command

Why:
  ConversationHandler spans many states
  State transitions cross command boundaries
  One file easier to manage for current size
  Still ~800 lines; refactor when it hits 1500
```

---

## Technical Decisions

```
File size limit: 10MB
  Why: Covers 99% of real code files
       Protects Supabase storage
       Large files shouldn't be in git anyway

Telegram webhook (not polling)
  Why: Render doesn't sleep with webhook traffic
       No need for keepalive pings to bot

Webhook auto-register on startup
  Why: No manual step to set webhook URL
       Bot recovers automatically on restart

Health check at /health
  Why: Render requires health check endpoint
       Also useful for monitoring

Channel logging (LOG_CHANNEL_ID)
  Why: Admin visibility into bot activity
       Error tracking without Sentry
```

---

## Decisions That Changed

```
Original Plan          → Current Actual
─────────────────────────────────────────
Koyeb hosting           → Render Docker
BYOD                    → Single Supabase
AES-256 encryption      → Plain text (SHA-256 auth)
JWT tokens              → API key (SHA-256 hash)
Branch from config      → Branch picker in bot flow
Scheduling first        → Deferred (FUTURE)
Multi-repo management   → Deferred (single for now)
Web fallback UI         → Deferred (FUTURE)
Keepalive system        → Deferred (FUTURE)
No admin commands       → Admin system implemented
No channel logging      → Channel logging implemented
No PR creation          → PR auto-creation implemented
```
