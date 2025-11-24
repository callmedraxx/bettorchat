#!/usr/bin/env python3
"""
Development server runner using uvicorn.
"""
import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        reload_dirs=["app"],
        log_level="debug" if settings.DEBUG else "info",
    )

