# ── Stage 1: Build ────────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# Install dependencies into a venv for clean copying
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Copy only the venv from builder (no build tools in final image)
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy ONLY backend source files — no extension/, no public/
COPY main.py          .
COPY bot.py           .
COPY admin.py         .
COPY github_service.py .
COPY diff_service.py  .
COPY supabase_service.py .
COPY models/          ./models/
COPY routes/          ./routes/

# Non-root user for security
RUN useradd -m -u 1001 gitphone
USER gitphone

# Render injects PORT at runtime
EXPOSE 8000

# Uvicorn — single worker (Render free = 512MB RAM)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
