# 05 — Security

## Current Security Posture (MVP)

```
MVP is functional but has known shortcuts.
All FUTURE improvements are documented here.

Current:
  ✅ API key authentication (SHA-256 hashed)
  ✅ GitHub Device Flow OAuth (no password sharing)
  ✅ Fine-grained PAT support (fallback)
  ✅ Telegram registered-user whitelist
  ✅ HTTPS in transit (Render provides TLS)
  ✅ Tokens never logged
  ✅ User ban system

Not Yet Implemented (FUTURE):
  ❌ AES-256 encryption for stored tokens
  ❌ HTTPS cert pinning
  ❌ Rate limiting on API routes
  ❌ Token rotation
  ❌ Telegram webhook secret token validation
```

---

## Authentication

### API Key System (Current — Fully Implemented)

```
Every request from the VS Code extension must include:
  X-Api-Key: <secret_key>
  X-Telegram-Id: <telegram_id>

The key is:
  1. Generated at registration as a 256-bit random token
  2. SHA-256 hashed before storage in Supabase
  3. Returned to the extension ONCE (never stored on backend)
  4. Sent with every subsequent request

Public endpoints (no auth):
  POST /register    ← generates the key
  GET  /health
  GET  /version
  POST /webhook     ← Telegram (validated by bot token)
```

### GitHub Device Flow OAuth (Current — Fully Implemented)

```
Users can authenticate via GitHub Device Flow:
  1. User sends /auth to the bot
  2. Bot requests device_code from GitHub
  3. User visits github.com/login/device and enters code
  4. Bot polls GitHub for token (background async task)
  5. Token stored in users.github_token (plain text for now)
  6. No PAT needed - works with just a browser

Fallback: Setup panel also supports PAT entry directly.
```

---

## Token Storage (MVP)

```
GitHub token stored as plain text in Supabase users table.

Risk: Supabase breach → tokens exposed.
Mitigation: Fine-grained PATs (limited scope repos only).
FUTURE: AES-256 encryption post MVP.
```

---

## GitHub Token Requirements

```
TYPE: Fine-grained Personal Access Token (PAT) OR OAuth token
Classic PAT also works but not recommended.

Required permissions:
  ✅ Repository access: specific repos only
  ✅ Permissions: Contents (read and write)

Why fine-grained:
  If token is stolen:
  - Can only access the specific repo
  - Can only read/write file contents
  - Cannot delete repo
  - Cannot access other repos
  - Blast radius is minimal ✅
```

---

## AES-256 Encryption (FUTURE)

```python
# Planned for post-MVP using pycryptodome
# pip install pycryptodome

from Crypto.Cipher import AES
from Crypto.Random import get_random_bytes
import base64

ENCRYPTION_KEY = bytes.fromhex(os.environ["ENCRYPTION_KEY"])  # 32 bytes

def encrypt_token(plaintext: str) -> str:
    nonce = get_random_bytes(16)
    cipher = AES.new(ENCRYPTION_KEY, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext.encode())
    combined = nonce + tag + ciphertext
    return base64.b64encode(combined).decode()
```

---

## Telegram Security

### Whitelist Approach (Current)
```python
# Every bot handler checks this first
async def _check_registered(update) -> Optional[dict]:
    telegram_id = str(update.effective_user.id)
    user = get_user_by_telegram_id(telegram_id)
    if not user:
        await update.effective_message.reply_text(...)
        return None
    if user.get("status") == "banned":
        await update.effective_message.reply_text(...)
        return None
    update_last_active(telegram_id)
    return user
```

---

## Rate Limiting (FUTURE)

```python
# Planned post-MVP:
# pip install slowapi
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

@router.post("/sync-file")
@limiter.limit("100/minute")
async def sync_file(...):
    ...
```

---

## Security TODOs (Ordered by Priority)

```
Priority 1 (Post-MVP):
  [ ] AES-256 encryption for github_token
  [ ] Telegram webhook secret token validation
  [ ] Add ENCRYPTION_KEY to Render env vars

Priority 2:
  [ ] Rate limiting on /sync-file and /register
  [ ] Request signature validation (HMAC)

Priority 3:
  [ ] BYOD migration
  [ ] Token rotation support
  [ ] Supabase RLS policies

Never:
  ❌ Store full file contents (only diffs)
  ❌ Log tokens anywhere
```
