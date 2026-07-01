# 15 — Demo Script

## Setup (Before Demo)

```
Required:
  ✅ VS Code open with a repo
  ✅ Extension connected (🟢 status bar showing)
  ✅ Telegram bot ready on phone
  ✅ GitHub repo visible on projector/laptop screen

Backup:
  ✅ Recorded demo GIF (~90 seconds)
  ✅ Screenshot of each step
```

---

## Script (90 Seconds)

### Step 1: The Problem (5 sec)
```
Speaker: "I'm a developer who forgot my laptop."

Show GitHub repo: no recent commits.
```

### Step 2: VS Code — Save A File (15 sec)
```
1. Open a file in VS Code
2. Make a simple edit (add a comment, fix a typo)
3. Save (Ctrl+S / Cmd+S)
4. Status bar updates:

   "🟢 GitPhone — 1 file staged"

Speaker: "Changes detected. Staged automatically."
```

### Step 3: Telegram — Commit From Phone (40 sec)
```
1. Pick up phone, open Telegram
2. Type /files
3. Bot shows:

   [Files] user/repo • main
   ☐ src/index.js  1.2KB

4. Tap file → checkmark appears ✅
5. Tap "Done"
6. Type: "fix: updated login logic"
7. Tap "Looks Good"
8. Branch picker shows:

   [OK] main (current)
   [Branch] develop
   [Branch] feature/login

9. Tap "main"
10. Review screen appears
11. Tap "Commit Now"

Speaker: "Three taps, one message. Real commit."
```

### Step 4: Verify On GitHub (15 sec)
```
1. Switch to laptop screen
2. Refresh GitHub repo
3. Show the commit:

   fix: updated login logic
   user committed 30 seconds ago
   🔗 abc123f

Speaker: "Real commit. From my phone."
```

### Step 5: Branch Flow (15 sec) — If Time Permits
```
1. Open another file, save it
2. /files, select, type message
3. Branch picker → "Create new branch..."
4. Type: "patch-1"
5. Commit → auto PR created
6. Show PR on GitHub:
   "patch-1 → main — fix: typo"

Speaker: "Even branches and PRs from my phone."
```

---

## Closing (15 sec)

```
Speaker:
  "GitPhone — because your GitHub streak
   shouldn't depend on carrying a laptop."

  "Open source. Links below."
```

---

## Backup Plan

```
If live demo fails:
  1. Switch to recorded GIF
  2. Narrate over it
  3. Same script, same timing

If GitHub API is slow:
  1. Pre-stage a file in Supabase
  2. Skip VS Code step
  3. Start from Telegram

If internet is down:
  1. Offline demo: show code on screen
  2. Show the GIF from local file
```

---

## Judge Questions + Answers

```
Q: "Is this just scheduled commits?"
A: "No. It's real-time. Save in VS Code,
    commit from phone. Also supports
    scheduling, but instant is the core."

Q: "What about conflicts?"
A: "We detect them via SHA comparison.
    You can force commit if you want,
    or switch branches. PR created for
    protected branches automatically."

Q: "Is my token safe?"
A: "It's a fine-grained PAT. Only
    specific repo, contents read/write.
    OAuth Device Flow means GitHub
    tokens never touch Telegram.
    AES-256 encryption incoming."

Q: "How is this different from
    GitHub mobile app?"
A: "VS Code integration. No app needed
    on phone. Works with any phone.
    Scheduling. Branch picker. PRs.
    Built for developers who code
    on laptop, manage from phone."

Q: "Open source?"
A: "Yes. Public repo with full docs.
    Self-hostable. Community contributions
    welcome."
```

---

## Technical Checks (Pre-Demo)

```
[ ] Status bar shows 🟢 before stage
[ ] /files loads within 2 seconds
[ ] File toggle works (callback query)
[ ] Commit creates visible SHA on GitHub
[ ] Branch picker loads (GitHub API fast)
[ ] PR creation works (if demoing)
[ ] Phone on airplane mode? Telegram works
[ ] Laptop screen mirrored correctly
[ ] Font size readable for audience
[ ] All passwords/tokens off screen
```
