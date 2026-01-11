# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Real estate title search automation platform with FastAPI backend, React frontend, and Celery task queue. Automates county recorder searches, document extraction, title chain analysis, and report generation.

## Development Commands

### Backend (from `/backend`)

```bash
# Setup
python -m venv venv && venv\Scripts\activate  # Windows
python -m venv venv && source venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
playwright install chromium
alembic upgrade head

# Run server
uvicorn app.main:app --reload --port 8000

# Run Celery worker (separate terminal)
celery -A tasks.celery_app worker --loglevel=info

# Testing
pytest tests/ -v                              # All tests
pytest tests/test_file_upload.py -v           # Single file
pytest tests/test_config.py::test_name -v     # Single test

# Formatting/Linting
black .
isort .
flake8 --max-line-length=120 --exclude=venv,__pycache__,.git
```

### Frontend (from `/frontend`)

```bash
npm install
npm run dev          # Dev server at http://localhost:5173
npm run build        # Production build
npm run lint         # ESLint
npx tsc --noEmit     # Type check
```

### Docker (full stack)

```bash
docker-compose up -d                                    # Start all services
docker-compose exec backend alembic upgrade head        # Run migrations
docker-compose logs -f backend                          # View logs
```

### Database Migrations

```bash
alembic revision --autogenerate -m "Description"   # Create migration
alembic upgrade head                               # Apply migrations
alembic downgrade -1                               # Rollback one
```

## Architecture

### Backend (`/backend/app`)

- **Entry point**: `main.py` - FastAPI application
- **Config**: `config.py` - Pydantic settings (DB URL conversion, JWT config, file upload limits)
- **Database**: `database.py` - Async SQLAlchemy with PostgreSQL
- **Models** (`models/`): 11 SQLAlchemy models - User, Search, Document, Report, Property, County, ChainOfTitle, Encumbrance, Batch, AuditLog, AiConfig
- **Routers** (`routers/`): API endpoints with `/api` prefix - auth, searches, documents, reports, batch, counties
- **Services** (`services/`): Business logic layer
- **Scraping** (`scraping/`): Playwright-based county recorder adapters
- **AI** (`ai/`): OpenAI/Anthropic integrations for document analysis

### Frontend (`/frontend/src`)

- **Entry**: `main.tsx` → `App.tsx`
- **State**: Zustand stores in `store/`
- **Data fetching**: TanStack Query in `lib/`
- **Styling**: Tailwind CSS

### Task Queue (`/backend/tasks`)

Celery workers handle long-running operations: web scraping, PDF generation, batch processing.

## Service Ports

| Service | Port |
|---------|------|
| Frontend | 5173 |
| Backend API | 8000 |
| PostgreSQL | 5432 |
| Redis | 6379 |
| MinIO (S3) | 9000/9001 |
| Flower (Celery UI) | 5555 |

## Key Patterns

- **Async-first**: All database operations use async SQLAlchemy with asyncpg
- **DATABASE_URL conversion**: Config automatically converts `postgresql://` to `postgresql+asyncpg://`
- **Background tasks**: Long-running operations (scraping, PDF generation) go through Celery
- **Document storage**: MinIO S3-compatible storage for uploaded/scraped documents
- **Browser pool**: Playwright browsers managed in a pool for county recorder scraping

## Environment Variables

Required:
- `DATABASE_URL` - PostgreSQL connection (async variant applied automatically)
- `REDIS_URL` - Redis connection
- `SECRET_KEY` - JWT signing key

Optional:
- `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` - AI features
- `BROWSER_HEADLESS=true`, `BROWSER_POOL_SIZE=5` - Scraping config
