# Chatbot API

FastAPI-based backend server optimized for AI chatbot applications with streaming support.

## Features

- 🚀 FastAPI with automatic Swagger/OpenAPI documentation
- 📡 Optimized for AI data streaming
- 🗄️ In-memory store for development (SQLite + dict)
- 🐘 PostgreSQL + Redis for production
- 🐳 Docker and Docker Compose support
- 🔄 Async/await support throughout
- 📝 Type hints and Pydantic validation

## Project Structure

```
bettorchat/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI application entry point
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py       # API router aggregator
│   │       └── endpoints/      # Endpoint modules (add your services here)
│   │           └── __init__.py
│   └── core/
│       ├── __init__.py
│       ├── config.py           # Application configuration
│       ├── database.py         # Database connection (SQLite/PostgreSQL)
│       └── redis_client.py     # Redis client (in-memory/Redis)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── run_dev.py                  # Development server script
├── setup_dev.sh                # Development setup script (Linux/macOS)
├── setup_dev.ps1               # Development setup script (Windows)
└── README.md
```

## Quick Start

### Development (In-Memory Store)

1. **Set up virtual environment:**
   
   **Linux/macOS:**
   ```bash
   ./setup_dev.sh
   ```
   
   **Windows (PowerShell):**
   ```powershell
   .\setup_dev.ps1
   ```
   
   **Manual setup:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

2. **Activate virtual environment (if not already active):**
   ```bash
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Copy environment file (optional):**
   ```bash
   cp .env.example .env
   ```

4. **Run development server:**
   ```bash
   python run_dev.py
   ```
   Or directly with uvicorn:
   ```bash
   uvicorn app.main:app --reload
   ```

5. **Access the API:**
   - API: http://localhost:8000
   - Swagger Docs: http://localhost:8000/docs
   - ReDoc: http://localhost:8000/redoc

**Note:** Remember to activate the virtual environment (`source venv/bin/activate`) each time you open a new terminal. To deactivate, simply run `deactivate`.

### Production (Docker with PostgreSQL & Redis)

1. **Start all services:**
   ```bash
   docker-compose up -d
   ```

2. **View logs:**
   ```bash
   docker-compose logs -f api
   ```

3. **Stop services:**
   ```bash
   docker-compose down
   ```

4. **Stop and remove volumes:**
   ```bash
   docker-compose down -v
   ```

## Configuration

Environment variables can be set in `.env` file:

- `ENVIRONMENT`: `development` or `production`
- `DATABASE_URL`: PostgreSQL connection string (empty for in-memory in dev)
- `REDIS_URL`: Redis connection string (empty for in-memory in dev)
- `DEBUG`: Enable debug mode
- `BACKEND_CORS_ORIGINS`: CORS allowed origins (JSON array)

## Adding Services

To add new API endpoints:

1. Create a new file in `app/api/v1/endpoints/` (e.g., `chat.py`)
2. Define your router with endpoints
3. Import and include it in `app/api/v1/router.py`

Example:
```python
# app/api/v1/endpoints/chat.py
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()

@router.post("/stream")
async def stream_chat():
    async def generate():
        # Your streaming logic here
        for chunk in your_ai_stream():
            yield f"data: {chunk}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")
```

Then in `app/api/v1/router.py`:
```python
from app.api.v1.endpoints import chat
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
```

## Streaming Support

The server is optimized for streaming responses. Use `StreamingResponse` for AI-generated content:

```python
from fastapi.responses import StreamingResponse

@router.post("/chat/stream")
async def stream_chat():
    async def generate():
        # Your AI streaming logic
        async for chunk in ai_model.stream():
            yield chunk
    return StreamingResponse(generate(), media_type="text/plain")
```

## Database

- **Development**: SQLite in-memory (no setup needed)
- **Production**: PostgreSQL (via Docker Compose)

Access database session:
```python
from app.core.database import get_db
from fastapi import Depends

@router.get("/items")
async def get_items(db: Session = Depends(get_db)):
    # Use db session
    pass
```

## Redis

- **Development**: In-memory Python dict (no setup needed)
- **Production**: Redis (via Docker Compose)

Access Redis:
```python
from app.core.redis_client import redis_client

# Sync
value = redis_client.get("key")
redis_client.set("key", "value", ex=3600)

# Async
value = await redis_client.aget("key")
await redis_client.aset("key", "value", ex=3600)
```

## API Documentation

FastAPI automatically generates interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/api/v1/openapi.json

## Production Deployment

The Docker setup uses:
- **Gunicorn** with Uvicorn workers (4 workers by default)
- **PostgreSQL** for persistent data
- **Redis** for caching and sessions

To customize workers:
```bash
docker-compose up -d --scale api=4
```

Or modify the Dockerfile CMD to adjust worker count.

## License

MIT

# bettorchat
