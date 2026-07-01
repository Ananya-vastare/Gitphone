# 13 — Open Source Roadmap

## Vision

```
After hackathon, GitPhone grows as an open source project.
Community contributions drive future development.

This roadmap is aspirational — dates are flexible.
```

---

## Now (MVP Complete)

```
Current state is demoable and useful.
Code is private. Needs cleanup before public release:

Public repo preparation:
  [ ] Remove all secrets and env var references
  [ ] Add CONTRIBUTING.md
  [ ] Add CODE_OF_CONDUCT.md
  [ ] Add LICENSE (MIT recommended)
  [ ] Clean up TODO comments
  [ ] Add issue templates
  [ ] Add PR template
  [ ] CI via GitHub Actions
```

---

## Phase 1: Cleanup (Week 1-2)

```
Code quality:
  [ ] Add proper type hints across backend
  [ ] Add docstrings to all functions
  [ ] Add comments for complex logic
  [ ] Standardize error responses
  [ ] Add request/response validation tests

Documentation:
  [ ] README with demo link
  [ ] Setup guide with screenshots
  [ ] API docs (auto from FastAPI + manually curated)
  [ ] Architecture decision records

Testing:
  [ ] Unit tests for diff_service.py
  [ ] Unit tests for auth.py
  [ ] Integration tests for sync flow
```

---

## Phase 2: Security & Infrastructure (Week 3-4)

```
  [ ] AES-256 encryption for github_token
  [ ] Rate limiting on API routes
  [ ] Telegram webhook secret validation
  [ ] Supabase RLS policies
  [ ] VS Code Marketplace publish
  [ ] CI/CD pipeline (GitHub Actions → Render)
```

---

## Phase 3: Features (Month 2)

```
  [ ] Scheduling (APScheduler)
  [ ] Multi-repo bot management
  [ ] Keepalive + dormancy system
  [ ] Staleness warnings (72hr)
  [ ] Commit scheduling
  [ ] Web fallback UI (if Telegram is down)
  [ ] Auto-merge conflicts
  [ ] E2E tests
```

---

## Phase 4: Scale (Month 3+)

```
  [ ] BYOD migration (each dev owns their Supabase)
  [ ] Full team/multi-user support
  [ ] Stats/analytics dashboard
  [ ] Custom domain
  [ ] Public roadmap board
  [ ] Community contributions guide
  [ ] Potential monetization:
      - Free: Open source, self-hosted
      - Paid: Managed hosting (Render Pro)
      - Paid: Premium features (teams, analytics)
```

---

## Contributing Guide (Planned)

```
Tech stack:
  Backend: Python 3.11+, FastAPI
  Bot: python-telegram-bot v21
  Extension: TypeScript
  DB: Supabase

Before PR:
  1. Read CONTRIBUTING.md
  2. Run lint + tests
  3. Update docs
  4. Add changelog entry

Areas needing help:
  - Web fallback UI (React/HTML + FastAPI templates)
  - VS Code extension testing
  - Documentation
  - Accessibility
  - i18n
```

---

## Public Repo Structure

```
gitphone-public/
├── README.md
├── CHANGELOG.md
├── LICENSE
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── setup/
│   └── schema.sql
├── migrations/
├── docs/
│   ├── setup-guide.md
│   ├── troubleshooting.md
│   ├── faq.md
│   └── security.md
└── .github/
    ├── ISSUE_TEMPLATE/
    └── workflows/
        └── ci.yml
```
