# Builds Odhu as ONE server: FastAPI serves the API and the built React app.
# Used by Render (see render.yaml); also works with any Docker host.
#
#   docker build -t odhu .
#   docker run -p 8000:8000 --env-file .env odhu      # then open http://localhost:8000

# ---- Stage 1: build the React frontend into static files ----
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- Stage 2: the Python backend, plus the built frontend ----
FROM python:3.12-slim
# uv, the package manager we use locally (pinned to the same version).
COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /bin/uv

WORKDIR /app/backend
# Install dependencies first (cached between deploys unless they change).
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./

# main.py serves ../frontend/dist when it exists.
COPY --from=frontend /app/frontend/dist /app/frontend/dist

# The SQLite database and cached audio live here. On Render's free plan this
# folder is reset on every deploy and restart.
ENV DATA_DIR=/app/backend/data
RUN mkdir -p /app/backend/data

# Render tells the app which port to use in $PORT; 8000 when running locally.
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uv run --no-dev uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
