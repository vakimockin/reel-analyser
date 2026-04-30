# Instagram Reels Analyzer

Minimal stack for testing Instagram Reels parsing, viral filtering, and AI analysis.

## Project Structure

- `backend/` - FastAPI API, services, database models, Alembic migrations, tests
- `frontend/` - minimal static landing page for manual API testing
- `docker-compose.yml` - orchestrates `db`, `backend`, `frontend`, and `telegram-bot`

## Requirements

- Docker + Docker Compose
- `.env` file in project root (used by `docker-compose.yml`)

Expected `.env` keys:

- `APIFY_TOKEN`
- `OPENAI_API_KEY`
- `OPENAI_MODEL` (optional, default in code is `gpt-4o`)

Optional AI tuning keys:

- `AI_MAX_REELS`
- `OPENAI_FRAMES_PER_REEL`
- `AI_THUMBNAIL_ONLY`
- `AI_NICHE_SUMMARY_ENABLED`
- `OPENAI_SUMMARY_MODEL`

Telegram bot keys:

- `TG_BOT_TOKEN` (required for bot service and run notifications)
- `TG_CHAT_ID` (required for automatic run notifications in a group/chat)
- `TELEGRAM_BOT_TOKEN` (legacy fallback supported)
- `TELEGRAM_ALLOWED_CHAT_IDS` (optional, comma-separated chat IDs)

## Run with Docker

```bash
docker compose up --build
```

Services:

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend API: [http://localhost:8000](http://localhost:8000)
- Postgres: `localhost:5432`
- Telegram bot: runs as polling worker (`telegram-bot` service)

Backend container startup command applies migrations automatically:

```bash
alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000
```

## Main API Endpoints

Base path: `/api/v1`

- `POST /analyze` - run scraping + viral filtering + AI analysis
- `GET /analyses` - list analysis runs
- `GET /analyses/{run_id}` - get full run details
- `POST /analyses/{run_id}/regenerate` - regenerate AI analysis for saved reels
- `GET /health` - health check

## Notes

- All prompts, UI text, and backend errors are in English.
- Backend code is fully scoped under `backend/`.
- Frontend is intentionally minimal and optimized for quick manual testing.
- Telegram bot commands:
  - `/start` and `/help`
  - `/latest` for recent runs
  - `/run <id>` for run details
- Automatic Telegram notification is sent after each `/api/v1/analyze` run when
  `TG_BOT_TOKEN` and `TG_CHAT_ID` are set.
