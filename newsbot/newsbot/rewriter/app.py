"""Rewriter service FastAPI application."""

import os
import uvicorn
from fastapi import FastAPI

from newsbot.core.settings import settings
from newsbot.core.logging import setup_logging, get_logger

# Setup logging
setup_logging("rewriter")
logger = get_logger(__name__)

app = FastAPI(title="NewsBot Rewriter", version="0.1.0")


@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return {"ok": True, "service": "rewriter"}


@app.get("/")
async def root():
    """Root endpoint."""
    service_name = os.getenv("SERVICE_NAME", "rewriter")
    version = os.getenv("SERVICE_VERSION", "0.1.0")
    return {"service": service_name, "version": version}


@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    logger.info("Starting rewriter service", extra={"service": "rewriter", "version": "0.1.0"})


# TODO: Add rewriter-specific endpoints


if __name__ == "__main__":
    logger.info("Starting rewriter service via uvicorn")
    uvicorn.run(
        "newsbot.rewriter.app:app",
        host=settings.service_host,
        port=settings.service_port or 8003,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )