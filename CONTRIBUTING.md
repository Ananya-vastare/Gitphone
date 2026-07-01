# Contributing to GitPhone

Welcome! GitPhone is participating in **ECSoC 2026** (Application ID: `zr7c9lnx0`).

## Before You Start
- Comment on an issue before starting work (avoid duplicate effort)
- Fork the repo, work on a feature branch, open a PR against `main`
- Every PR **must** have the `ECSoC26` label to be scored by ECSoC Sentinel

## PR Rules
- One feature/fix per PR
- Write a clear description of what changed and why
- Backend PRs: run `ruff check backend/` before pushing
- Extension PRs: run `npx tsc --noEmit` before pushing
- Do not include secrets, tokens, or `.env` files

## Scoring (Automated by ECSoC Sentinel)
Once a PR with the `ECSoC26` label is merged, ECSoC Sentinel automatically assigns a difficulty label and updates the public leaderboard.

| Label | Points | Difficulty |
|---|---|---|
| `ECSoC26-L1` | 5 pts | Easy |
| `ECSoC26-L2` | 10 pts | Medium |
| `ECSoC26-L3` | 15 pts | Difficult |

## Bonus XP (awarded by Admin at discretion)

| Label | Bonus XP | When used |
|---|---|---|
| `good-issue` | +10 XP | Well-researched issue report |
| `good-pr` | +15 XP | Exceptionally clean PR |
| `good-ui` | +25 XP | Outstanding UI/UX contribution |
| `good-backend` | +50 XP | Exceptional backend contribution |