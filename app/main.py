"""
FastAPI application entry point for chatbot backend.
Optimized for AI workloads with streaming support.
"""
import logging
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.api.v1.router import api_router
from app.core.database import engine, Base
from app.models import Fixture  # Import models to register them
from app.models.tool_result import ToolResult  # Import ToolResult model to register it
from app.models.odds_entry import OddsEntry  # Import OddsEntry model to register it
from app.models.nfl_player import NFLPlayer  # Import NFLPlayer model to register it
from app.models.nfl_fixture import NFLFixture  # Import NFLFixture model to register it
from app.models.nfl_odds import NFLOdds  # Import NFLOdds model to register it
from app.core.nfl_fixture_polling import nfl_fixture_polling_service
from app.core.nfl_odds_polling import nfl_odds_polling_service

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

# Set log level for uvicorn/gunicorn
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)
logging.getLogger("gunicorn").setLevel(logging.INFO)
logging.getLogger("gunicorn.error").setLevel(logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup - create database tables (ignore errors if tables already exist)
    logger = logging.getLogger(__name__)
    try:
        # Use checkfirst=True to avoid errors if tables already exist
        Base.metadata.create_all(bind=engine, checkfirst=True)
        logger.info("Database tables created/verified successfully")
    except Exception as e:
        # Log but don't fail startup if tables already exist or there are type conflicts
        error_msg = str(e)
        if "already exists" in error_msg or "DuplicateTable" in error_msg or "UniqueViolation" in error_msg:
            logger.info(f"Database tables already exist - skipping creation: {error_msg[:200]}")
        else:
            logger.warning(f"Database table creation warning: {error_msg[:200]}")
        # Try to verify connection works
        try:
            with engine.connect() as conn:
                from sqlalchemy import text
                conn.execute(text("SELECT 1"))
            logger.info("Database connection verified")
        except Exception as conn_error:
            logger.error(f"Database connection error: {conn_error}")
            # Don't raise - let the app start and handle DB errors at runtime
    
    # Pre-warm agent cache for faster first response
    try:
        from app.agents.agent import create_betting_agent
        logger.info("Pre-warming agent cache for faster responses...")
        # Create agent instance in background to cache it
        # This avoids agent creation overhead on first request
        agent = create_betting_agent(use_cache=True)
        logger.info("Agent cache pre-warmed successfully")
    except Exception as e:
        logger.warning(f"Failed to pre-warm agent cache: {e} (this is non-critical)")
    
    # Start NFL fixture polling service
    try:
        await nfl_fixture_polling_service.start_polling()
        logger.info("NFL fixture polling service started")
    except Exception as e:
        logger.error(f"Failed to start NFL fixture polling service: {e}", exc_info=True)
        # Don't fail startup if polling service fails
    
    # Start NFL odds polling service
    try:
        await nfl_odds_polling_service.start_polling()
        logger.info("NFL odds polling service started")
    except Exception as e:
        logger.error(f"Failed to start NFL odds polling service: {e}", exc_info=True)
        # Don't fail startup if polling service fails
    
    yield
    
    # Shutdown - stop polling services
    try:
        await nfl_fixture_polling_service.stop_polling()
        logger.info("NFL fixture polling service stopped")
    except Exception as e:
        logger.error(f"Error stopping NFL fixture polling service: {e}", exc_info=True)
    
    try:
        await nfl_odds_polling_service.stop_polling()
        logger.info("NFL odds polling service stopped")
    except Exception as e:
        logger.error(f"Error stopping NFL odds polling service: {e}", exc_info=True)


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Chatbot API with AI streaming support",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware - Allow all Lovable project origins, bettorchat.app, and configured origins
# Use allow_origin_regex to match any subdomain pattern for Lovable projects and bettorchat domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_origin_regex=r"https?://.*\.lovableproject\.com|https?://.*\.lovable\.dev|https?://.*\.lovable\.app|https?://.*\.bettorchat\.app",  # Allow any subdomain (removed $ to allow paths)
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH", "HEAD"],  # Explicitly include OPTIONS for preflight
    allow_headers=["*"],
    expose_headers=["*"],  # Expose all headers for streaming endpoints
    max_age=3600,  # Cache preflight requests for 1 hour
)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Chatbot API",
        "version": settings.VERSION,
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}

