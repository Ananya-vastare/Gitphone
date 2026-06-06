-- Run this in Supabase SQL Editor (Database → SQL Editor → New query)
-- Required for GitPhone v1.4.0

-- 1. Active repo tracking (auto-detected from VS Code)
ALTER TABLE users ADD COLUMN IF NOT EXISTS active_repo    TEXT;
ALTER TABLE users ADD COLUMN IF NOT EXISTS active_branch  TEXT;

-- 2. Ban reason column for admin /ban command
ALTER TABLE users ADD COLUMN IF NOT EXISTS ban_reason     TEXT;

-- 3. Per-file repo tracking (for grouped /files view)
ALTER TABLE staged_files ADD COLUMN IF NOT EXISTS repo    TEXT;

-- 4. (Already done in previous session) API key hash
ALTER TABLE users ADD COLUMN IF NOT EXISTS api_key_hash   TEXT;

-- Verify columns exist
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name IN ('users', 'staged_files')
  AND column_name IN ('active_repo', 'active_branch', 'ban_reason', 'repo', 'api_key_hash')
ORDER BY table_name, column_name;

-- 5. Track file change type for grouped display in bot
ALTER TABLE staged_files ADD COLUMN IF NOT EXISTS change_type TEXT DEFAULT 'modify';
