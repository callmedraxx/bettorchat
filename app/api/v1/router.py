"""
API v1 router - aggregates all endpoint routers.
"""
from fastapi import APIRouter

# Import routers here as you add them
# from app.api.v1.endpoints import chat, auth, etc.
from app.api.v1.endpoints import example_stream, agent

api_router = APIRouter()

# Include endpoint routers here
# api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
# api_router.include_router(auth.router, prefix="/auth", tags=["auth"])

# Agent endpoints
api_router.include_router(
    agent.router,
    prefix="/agent",
    tags=["agent"]
)

# Example streaming endpoint (remove when adding your services)
api_router.include_router(
    example_stream.router,
    prefix="/example",
    tags=["example"]
)


@api_router.get("/")
async def api_root():
    """API root endpoint."""
    return {"message": "API v1", "status": "ready"}

