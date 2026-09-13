# PNU Smart Educational Assistant — Railway Docker image
FROM python:3.11-slim

WORKDIR /app

# system deps (pydantic core, bcrypt wheels usually exist; keep slim)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && rm -rf /var/lib/apt/lists/*

# python deps
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# frontend build (node stage)
FROM node:20-slim AS fe
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ .
RUN npm run build

# final image
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY --from=fe /fe/dist /app/backend/frontend_dist
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend /app/backend
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

ENV PORT=8000
ENV CORS_ORIGINS="*"
EXPOSE 8000
CMD ["/app/start.sh"]
