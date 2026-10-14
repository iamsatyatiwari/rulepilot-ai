# Single Cloud Run service: FastAPI serves the API and the built dashboard.
FROM node:22-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1     PYTHONUNBUFFERED=1     PORT=8080     RULEPILOT_STATIC_DIR=/app/static     RULEPILOT_DATA_DIR=/tmp/rulepilot
WORKDIR /app
COPY backend/requirements-lock.txt ./
RUN pip install --no-cache-dir -r requirements-lock.txt
COPY backend/app ./app
COPY --from=frontend /build/frontend/dist ./static
RUN useradd --create-home --uid 10001 rulepilot && chown -R rulepilot /app
USER rulepilot
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers"]
