# Title Search Application

A real estate title search application with FastAPI backend and React frontend. Automates county recorder searches, document extraction, title chain analysis, and report generation.

## Features

- **Automated Title Searches** - Search county recorder databases for property records
- **Document Management** - Upload, store, and organize title documents
- **Chain of Title Analysis** - Automated analysis of ownership history
- **Encumbrance Detection** - Identify liens, easements, and other encumbrances
- **AI-Powered Document Processing** - OCR and intelligent document parsing
- **Report Generation** - Generate professional title reports in PDF format
- **Batch Processing** - Process multiple searches via CSV upload
- **User Authentication** - Secure JWT-based authentication with password reset

## Tech Stack

### Backend
- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - Async ORM with PostgreSQL
- **Celery** - Distributed task queue for background jobs
- **Redis** - Message broker and caching
- **Playwright** - Browser automation for web scraping
- **OpenAI/Anthropic** - AI-powered document analysis

### Frontend
- **React 18** - UI framework
- **TypeScript** - Type-safe JavaScript
- **Vite** - Build tool
- **TanStack Query** - Data fetching and caching
- **Zustand** - State management
- **Tailwind CSS** - Utility-first styling

### Infrastructure
- **PostgreSQL** - Primary database
- **Redis** - Task queue and caching
- **MinIO** - S3-compatible document storage
- **Docker** - Containerization

## Prerequisites

- **Docker & Docker Compose** (recommended) OR:
  - Python 3.11+
  - Node.js 18+
  - PostgreSQL 15+
  - Redis 7+

## Quick Start with Docker

1. **Clone the repository**
   ```bash
   git clone https://github.com/DataisKing1/title-search-app.git
   cd title-search-app
   ```

2. **Create environment file**
   ```bash
   cp .env.example .env
   ```

3. **Start all services**
   ```bash
   docker-compose up -d
   ```

4. **Access the application**
   - Frontend: http://localhost:5173
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs
   - Flower (Celery monitoring): http://localhost:5555
   - MinIO Console: http://localhost:9001

## Manual Setup

### Backend Setup

1. **Create and activate virtual environment**
   ```bash
   cd backend
   python -m venv venv

   # Windows
   venv\Scripts\activate

   # macOS/Linux
   source venv/bin/activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright browsers**
   ```bash
   playwright install chromium
   ```

4. **Set up environment variables**
   ```bash
   cp ../.env.example .env
   # Edit .env with your configuration
   ```

5. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

6. **Start the backend server**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

7. **Start Celery worker** (in a separate terminal)
   ```bash
   celery -A tasks.celery_app worker --loglevel=info
   ```

### Frontend Setup

1. **Install dependencies**
   ```bash
   cd frontend
   npm install
   ```

2. **Set up environment variables**
   ```bash
   echo "VITE_API_URL=http://localhost:8000/api" > .env.local
   ```

3. **Start development server**
   ```bash
   npm run dev
   ```

## Environment Variables

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://user:pass@localhost:5432/title_search` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `SECRET_KEY` | JWT signing key (32+ chars in production) | `your-secret-key` |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `OPENAI_API_KEY` | OpenAI API key for AI features | - |
| `ANTHROPIC_API_KEY` | Anthropic API key for AI features | - |
| `BROWSER_HEADLESS` | Run browser in headless mode | `true` |
| `BROWSER_POOL_SIZE` | Number of browser instances | `5` |
| `DEBUG` | Enable debug mode | `false` |

See `.env.example` for all available options.

## Running Tests

### Backend Tests
```bash
cd backend
pytest tests/ -v
```

### Frontend Build Check
```bash
cd frontend
npm run build
```

## Project Structure

```
title-search-app/
├── backend/
│   ├── app/
│   │   ├── models/          # SQLAlchemy models
│   │   ├── routers/         # API endpoints
│   │   ├── services/        # Business logic
│   │   ├── scraping/        # Web scraping adapters
│   │   └── config.py        # Configuration
│   ├── tasks/               # Celery tasks
│   ├── tests/               # Backend tests
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── pages/           # Page components
│   │   ├── lib/             # API client, utilities
│   │   └── store/           # Zustand stores
│   └── package.json
├── docker-compose.yml
└── .env.example
```

## API Documentation

Once the backend is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Development

### Code Style

**Backend:**
```bash
# Format code
black .
isort .

# Lint
flake8
```

**Frontend:**
```bash
# Lint
npm run lint

# Type check
npx tsc --noEmit
```

## CI/CD

This project uses GitHub Actions for continuous integration and deployment.

### Workflows

| Workflow | Trigger | Description |
|----------|---------|-------------|
| **CI** | Push/PR to main | Runs tests, linting, and builds |
| **Security** | Push/PR + Weekly | Dependency scanning and CodeQL analysis |
| **Deploy** | Manual/Release | Builds and pushes Docker images to GHCR |

### CI Pipeline

On every push and pull request:
- **Backend Tests** - Runs pytest with PostgreSQL and Redis services
- **Backend Lint** - Checks code formatting with Black, isort, and flake8
- **Frontend Build** - Type checks, lints, and builds the React app
- **Docker Build** - Validates Docker images build successfully (main branch only)

### Deployment

To deploy manually:
1. Go to Actions > Deploy > Run workflow
2. Select the environment (staging/production)
3. Click "Run workflow"

For automatic deployment, create a release tag:
```bash
git tag v1.0.0
git push origin v1.0.0
```

### Required Secrets

For deployment, configure these secrets in your repository:

| Secret | Description |
|--------|-------------|
| `RAILWAY_TOKEN` | Railway deployment token (if using Railway) |
| `VERCEL_TOKEN` | Vercel deployment token (if using Vercel) |
| `VERCEL_ORG_ID` | Vercel organization ID |
| `VERCEL_PROJECT_ID` | Vercel project ID |

## License

MIT License - see LICENSE file for details.
