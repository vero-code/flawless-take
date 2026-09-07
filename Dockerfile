# ==============================================================================
# Flawless Take - Production Cloud Run & Dockerfile
# Stage 1: Build React 19 Frontend
# Stage 2: Production Python 3.11 FastAPI Backend + Static SPA
# ==============================================================================

# --- Stage 1: Build Frontend ---
FROM node:20-alpine AS frontend-builder
WORKDIR /app

# Install dependencies first for build caching
COPY package*.json tsconfig*.json vite.config.ts index.html ./
RUN npm ci

# Copy source code and build production bundle
COPY public/ ./public/
COPY src/ ./src/
RUN npm run build

# --- Stage 2: Production Serverless Container ---
FROM python:3.11-slim AS production

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    PYTHONPATH=/app/backend

WORKDIR /app

# Install system utilities
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy compiled frontend from Stage 1
COPY --from=frontend-builder /app/dist /app/dist

# Copy backend application source
COPY backend/ /app/backend/

# Create uploads directory for camera captures
RUN mkdir -p /app/backend/uploads

EXPOSE 8080

# Cloud Run Container Health Check Probe
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/api/health || exit 1

# Launch production server on Cloud Run $PORT
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
