# Muse Alarm Clock — single-container build.
# Stage 1 builds the React dashboard; stage 2 runs the FastAPI backend
# which also serves the built dashboard as a single-page app.
FROM node:20-slim AS frontend
WORKDIR /build
COPY app/package.json app/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY app/ ./
RUN npm run build

FROM python:3.12-slim AS backend
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

# Server + device driver requirements.
COPY server/requirements.txt ./server-requirements.txt
COPY device/tc002/requirements.txt ./tc002-requirements.txt
RUN pip install --no-cache-dir -r server-requirements.txt -r tc002-requirements.txt

# App code.
COPY server/ ./server/
COPY device/ ./device/
# Built dashboard -> /app/frontend (served by FastAPI, see main.py).
COPY --from=frontend /build/dist ./frontend/

WORKDIR /app/server
# SQLite DB lives in /data (a volume in compose) so sequences survive updates.
ENV DB_PATH=/data/alarm-clock.db
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
