# 01 — Product

## Problem Statement

```
Developers maintain GitHub contribution streaks
as a signal of consistency and activity.

When a developer leaves their laptop at home
or is away from their workstation, they cannot
make commits. The streak breaks.

Existing solutions:
- GitHub mobile app: can edit files but clunky
- GitHub web editor: works but no local code context
- Remote desktop: requires laptop to be on
```

---

## Solution

```
GitPhone is a three-part system:

1. VS Code Extension
   Runs silently on developer's machine
   Watches for file saves
   Computes diffs and syncs to cloud
   Developer codes normally, nothing changes

2. Cloud Backend (Render)
   Always online, always listening
   Stores staged diffs per user
   Handles GitHub API commits
   Runs Telegram bot

3. Telegram Bot
   Developer's remote control from phone
   Shows staged files as tappable buttons
   Developer selects files, types message, picks branch
   Tap commit → real GitHub commit happens (with auto PR)
```

---

## Core Use Case

```
Morning:
  Developer codes on laptop as normal
  VS Code extension silently stages diffs
  Developer leaves home without laptop

Evening (out at dinner):
  Opens Telegram on phone
  /files → sees changed files as buttons
  Taps files to select
  Types commit message
  Picks branch (or creates new one)
  Taps Commit
  Real commit appears on GitHub ✅
  Streak maintained ✅
```

---

## Target User

```
Primary:
  Solo developers maintaining GitHub streaks
  Personal project developers
  Developers who work from a single machine

Secondary (FUTURE):
  Small dev teams
  Open source contributors
```

---

## What Makes GitPhone Unique

```
1. File selection via Telegram inline buttons
   No other tool lets you pick specific files
   from a chat interface

2. VS Code as the silent bridge
   No workflow change for the developer
   Just code normally, extension handles rest

3. Real commits, not synthetic
   Actual GitHub commits via API
   Real SHA, real history, real streak

4. Branch picker + auto PR creation
   Commit to any branch, get a PR link instantly

5. Always available
   Backend runs 24/7 on Render
   No laptop needed after staging
```

---

## MVP Success Criteria

```
For MVP to be considered successful:

✅ Developer saves a file in VS Code
✅ Diff appears in Supabase (verified)
✅ /files on Telegram shows that file
✅ Developer selects file via button
✅ Types commit message
✅ Picks branch (or uses default)
✅ Taps commit → real commit on GitHub
✅ Works end to end in under 90 seconds
```
