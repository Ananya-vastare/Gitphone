# 10 — Deployment

## Hosting Platform: Render

```
Why Render:
  Free tier: YES
  No credit card: YES
  Docker support: YES (actual deployment)
  Does not sleep in webhook mode: YES
  PostgreSQL: Optional (using Supabase instead)

Deployment method: Docker (Dockerfile + render.yaml)

Note: Koyeb was initially considered but requires credit card.
Vercel is unsuitable for long-running processes (serverless).
```

---

## render.yaml

```yaml
services:
  - type: web
    name: gitphone-backend
    runtime: docker
    repo: https://github.com/your-user/gitphone-backend
    plan: free
    env: docker
    dockerfilePath: ./Dockerfile
    healthCheckPath: /health
    autoDeploy: true
    envVars:
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_SERVICE_KEY
        sync: false
      - key: TELEGRAM_BOT_TOKEN
        sync: false
      - key: GITHUB_CLIENT_ID
        sync: false
      - key: GITHUB_CLIENT_SECRET
        sync: false
      - key: GITHUB_APP_NAME
        value: GitPhone
      - key: ADMIN_TELEGRAM_IDS
        sync: false
      - key: LOG_CHANNEL_ID
        sync: false
      - key: WEBHOOK_URL
        sync: false
      - key: PORT
        value: 8000
```

---

## Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Set environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Run with uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Env Vars (Production)

```
# === REQUIRED ===
# Supabase (your central DB)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJ...service_role_key

# Telegram
TELEGRAM_BOT_TOKEN=123456:ABC-DEF1234ghIkl...
WEBHOOK_URL=https://your-service.onrender.com

# GitHub OAuth (Device Flow)
GITHUB_CLIENT_ID=Iv1...23abc
GITHUB_CLIENT_SECRET=abc123...
GITHUB_APP_NAME=GitPhone

# === OPTIONAL ===
# Admin
ADMIN_TELEGRAM_IDS=123456789,987654321
LOG_CHANNEL_ID=-1001234567890
```

---

## Setup Steps

```
1. Create Supabase project
   - Go to https://supabase.com
   - New project
   - Run schema from public/setup/schema.sql in SQL editor
   - Copy Project URL and service_role key

2. Create Telegram bot
   - Message @BotFather
   - /newbot → name: GitPhone, username: @YourBotName
   - Copy bot token

3. Create GitHub OAuth App
   - Settings → Developer Settings → OAuth Apps
   - New OAuth App
   - Homepage: https://your-service.onrender.com
   - Callback: (not needed for Device Flow)
   - Copy Client ID + Client Secret

4. Deploy to Render
   - Connect GitHub repo
   - Set render.yaml env vars (paste values from steps 1-3)
   - Deploy (takes ~3 minutes first build)

5. Set Telegram webhook
   - Bot auto-registers webhook on startup:
     https://api.telegram.org/bot<TOKEN>/setWebhook
     ?url=https://your-service.onrender.com/webhook
   - Verified in bot startup logs

6. Test
   - Message @YourBotName on Telegram
   - Send /start
   - You should see the welcome message
```

---

## Environment Variable Management

```
Render dashboard → Environment tab → Add env vars
Supabase service_role key is NOT the anon key.
WEBHOOK_URL must be set before first deployment.
```

---

## Health Check

```
GET /health → 200 { "status": "ok" }

Render pings this every 5 minutes.
Service is always awake due to webhook traffic.
```

---

## Logs

```
Render dashboard → Logs tab
Channel logging: If LOG_CHANNEL_ID set,
admin actions and errors logged to Telegram channel.
```

---

## FUTURE Improvements

```
- Add .env.example to repo
- Document Redis for rate limiting
- Document Sentry for error tracking
- Add staging branch for testing
```
