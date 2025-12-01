"""
Application configuration settings.
"""
from typing import List, Optional, Union
import json
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """Application settings."""
    
    # Project
    PROJECT_NAME: str = "Chatbot API"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # CORS
    BACKEND_CORS_ORIGINS: Union[List[str], str] = Field(
        default=["http://localhost:3000", "http://localhost:8000", "https://lovable.dev", "https://bettorchat.app"]
    )
    
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse CORS origins from string or list."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [origin.strip() for origin in v.split(",")]
        return v
    
    # Environment
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=True)
    
    # Database (PostgreSQL for production)
    DATABASE_URL: Optional[str] = Field(default=None)
    DB_POOL_SIZE: int = Field(default=5)
    DB_MAX_OVERFLOW: int = Field(default=10)
    
    # Redis
    REDIS_URL: Optional[str] = Field(default="redis://localhost:6379/0")
    REDIS_HOST: str = Field(default="localhost")
    REDIS_PORT: int = Field(default=6379)
    REDIS_DB: int = Field(default=0)
    
    # Server
    HOST: str = Field(default="0.0.0.0")
    PORT: int = Field(default=8000)
    
    # Streaming
    STREAMING_CHUNK_SIZE: int = Field(default=1024)
    
    # AI Agents
    TAVILY_API_KEY: Optional[str] = Field(default=None)
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None)
    GOOGLE_API_KEY: Optional[str] = Field(default=None)  # For Gemini models
    
    # OpticOdds API
    OPTICODDS_API_KEY: Optional[str] = Field(default="f8a621e8-2583-4e97-a769-e70c99acdb85")
    
    # LangSmith (for tracing and monitoring)
    LANGSMITH_API_KEY: Optional[str] = Field(default=None)
    LANGSMITH_TRACING: Optional[str] = Field(default=None)
    LANGSMITH_ENDPOINT: Optional[str] = Field(default=None)
    LANGSMITH_PROJECT: Optional[str] = Field(default=None)
    
    # LangGraph (for deployed agents)
    LANGGRAPH_API_KEY: Optional[str] = Field(default=None)
    LANGGRAPH_API_URL: Optional[str] = Field(default=None)
    LANGGRAPH_AGENT_ID: Optional[str] = Field(default=None)
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

