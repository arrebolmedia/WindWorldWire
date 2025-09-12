"""Base FastAPI service with common functionality."""
from datetime import datetime
from fastapi import FastAPI, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from newsbot.core.database import get_db
from newsbot.core.logging import setup_logging, get_logger
from newsbot.core.settings import settings


def create_app(service_name: str) -> FastAPI:
    """Create FastAPI application with common configuration."""
    # Setup logging
    setup_logging(service_name)
    logger = get_logger(__name__)
    
    app = FastAPI(
        title=f"NewsBot - {service_name.title()}",
        description=f"WindWorldWire NewsBot {service_name} service",
        version="0.1.0",
        docs_url=f"/docs",
        redoc_url=f"/redoc",
    )
    
    @app.get("/healthz")
    async def health_check(db: AsyncSession = Depends(get_db)):
        """Health check endpoint."""
        try:
            # Test database connection
            await db.execute("SELECT 1")
            logger.info(f"{service_name} health check passed")
            return JSONResponse(
                status_code=200,
                content={
                    "status": "healthy",
                    "service": service_name,
                    "version": "0.1.0",
                    "timestamp": str(datetime.utcnow()),
                }
            )
        except Exception as e:
            logger.error(f"{service_name} health check failed: {e}")
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "service": service_name,
                    "error": str(e),
                    "timestamp": str(datetime.utcnow()),
                }
            )
    
    return app