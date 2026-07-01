# 04 — Database

## Overview

```
ONE central Supabase (yours) for MVP.
All users share one DB isolated by telegram_id.
BYOD (Bring Your Own Database) is FUTURE.
```

---

## Current Schema (Matches Actual Code)

```sql
-- ============================================================
-- GITPHONE CURRENT SCHEMA
-- One database, all users, separated by telegram_id
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- TABLE: users
-- Stores one row per registered developer
-- ============================================================
CREATE TABLE users (
  id                UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  telegram_id       TEXT NOT NULL UNIQUE,
  github_token      TEXT NOT NULL,          -- plain text (AES-256 is FUTURE)
  default_repo      TEXT NOT NULL,          -- "username/repo-name"
  branch            TEXT NOT NULL DEFAULT 'main',
  active_repo       TEXT,                   -- auto-detected from VS Code .git/config
  active_branch     TEXT,                   -- auto-detected from VS Code .git/HEAD
  timezone          TEXT NOT NULL DEFAULT 'UTC',
  schema_version    INT NOT NULL DEFAULT 1,
  api_key_hash      TEXT,                   -- SHA-256 hash of per-user API key
  last_active       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status            TEXT NOT NULL DEFAULT 'active',
                    -- values: active | banned
  ping_count        INT NOT NULL DEFAULT 0, -- FUTURE: keepalive pings
  device_flow_state TEXT,                   -- JSON blob for GitHub OAuth state
  ban_reason        TEXT,                   -- reason if status='banned'
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_telegram_id ON users(telegram_id);
CREATE INDEX idx_users_status ON users(status);

-- ============================================================
-- TABLE: staged_files
-- Stores diffs waiting to be committed via Telegram bot
-- ============================================================
CREATE TABLE staged_files (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  telegram_id   TEXT NOT NULL,             -- denormalized for fast bot queries
  filepath      TEXT NOT NULL,             -- relative path from workspace root
  diff          TEXT,                      -- unified diff patch (NULL if binary or full content)
  full_content  TEXT,                      -- base64 content (binary/new files)
  base_sha      TEXT NOT NULL,             -- git SHA diff was computed against
  is_binary     BOOLEAN NOT NULL DEFAULT FALSE,
  file_size     INT NOT NULL DEFAULT 0,    -- bytes
  repo          TEXT,                      -- auto-detected repo name
  change_type   TEXT NOT NULL DEFAULT 'modify',
                -- values: modify | create | delete
  status        TEXT NOT NULL DEFAULT 'pending',
                -- values: pending | committed | expired | cancelled
  staged_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One pending diff per file per user (new save overwrites old diff)
CREATE UNIQUE INDEX idx_staged_files_unique_pending
  ON staged_files(telegram_id, filepath)
  WHERE status = 'pending';

CREATE INDEX idx_staged_files_user_status
  ON staged_files(user_id, status);

CREATE INDEX idx_staged_files_telegram_pending
  ON staged_files(telegram_id, status);

-- ============================================================
-- TABLE: commit_log
-- Audit trail of every commit made via GitPhone
-- ============================================================
CREATE TABLE commit_log (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  telegram_id   TEXT NOT NULL,
  commit_sha    TEXT NOT NULL,
  message       TEXT NOT NULL,
  files         TEXT[] NOT NULL,           -- array of filepaths committed
  repo          TEXT NOT NULL,
  branch        TEXT NOT NULL DEFAULT 'main',
  was_scheduled BOOLEAN NOT NULL DEFAULT FALSE, -- FUTURE: will be used
  committed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_commit_log_user ON commit_log(user_id, committed_at DESC);
CREATE INDEX idx_commit_log_telegram ON commit_log(telegram_id, committed_at DESC);
```

---

## Table Relationships

```
users
  ↓ (one to many)
staged_files  (user_id → users.id)
  ↓
commit_log    (user_id → users.id)
```

---

## Key Design Decisions

```
1. telegram_id denormalized in staged_files
   → Avoids JOIN on every bot message
   → Bot queries are telegram_id-first

2. Unique index on pending staged files
   → One diff per file at a time
   → New save replaces old pending diff
   → Index uses telegram_id (not user_id) to match queries

3. full_content column for binary/new files
   → Binary files can't be diffed
   → Stored as base64 in this column
   → diff column is NULL for binary

4. repo + change_type columns
   → Files grouped by repo in bot UI
   → change_type shows create/modify/delete icons
   → repo auto-detected from VS Code .git/config

5. api_key_hash for authentication
   → SHA-256 hash of per-user API key
   → Generated at registration, returned once
   → Sent as X-Api-Key header on all requests

6. device_flow_state for GitHub OAuth
   → JSON blob storing device code + expiry
   → Used during GitPhone Device Flow auth
   → Cleaned up after auth completes/expires

7. status = 'active' | 'banned'
   → FUTURE will add 'inactive_7d' | 'dormant'
   → For now only active/banned used
```

---

## FUTURE Tables (Not Yet Implemented)

```
The following are planned for post-MVP:

-- scheduled: APScheduler-based scheduled commits
CREATE TABLE scheduled (
  id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  file_ids       UUID[] NOT NULL,
  commit_message TEXT NOT NULL,
  fire_at        TIMESTAMPTZ NOT NULL,
  status         TEXT NOT NULL DEFAULT 'pending',
  retries        INT NOT NULL DEFAULT 0,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- repos: Multi-repo support
CREATE TABLE repos (
  id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  repo_name  TEXT NOT NULL UNIQUE,
  branch     TEXT NOT NULL DEFAULT 'main',
  is_active  BOOLEAN NOT NULL DEFAULT FALSE,
  added_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## Storage Estimates

```
Per active user per month:
  staged_files:  ~50 diffs × ~500 bytes avg = 25KB
  commit_log:    ~30 commits × 200 bytes    = 6KB
  Total per user: ~31KB/month

Supabase free tier: 500MB
Users at free tier: ~16,000 users
Well within free limits ✅
```
