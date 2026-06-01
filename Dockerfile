# ── Stage 1: Build Frontend ────────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

# Copy package descriptors first to cache dependencies
COPY frontend/package*.json ./
RUN npm ci

# Copy frontend codebase and compile assets
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Serve API & Built Client Assets ──────────────────────────────
FROM python:3.11-slim
WORKDIR /app

# Install system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Cache PIP dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application
COPY main.py ./
COPY src/ ./src/
COPY templates/ ./templates/

# Copy compiled frontend assets from Builder stage
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create persistent storage folder for SQLite DB volume mounting
RUN mkdir -p /app/data
ENV DB_PATH=/app/data/marketing.db
ENV PORT=8000

# Expose FastAPI port
EXPOSE 8000

# Launch Uvicorn using the PORT environment variable injected by Render
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
