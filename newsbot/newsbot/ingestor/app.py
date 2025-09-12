"""Ingestor service FastAPI application."""

import os
import yaml
from pathlib import Path
import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any

from newsbot.core.settings import settings
from newsbot.core.logging import setup_logging, get_logger
from newsbot.ingestor.pipeline import run_ingest

# Setup logging
setup_logging("ingestor")
logger = get_logger(__name__)

app = FastAPI(title="NewsBot Ingestor", version="0.1.0")


class RunIngestResponse(BaseModel):
    """Response model for ingestion run."""
    status: str
    message: str
    stats: Dict[str, Any]


def load_config() -> Dict[str, Any]:
    """Load configuration from YAML file."""
    config_path = Path("config/sources.yaml")
    
    if not config_path.exists():
        logger.warning(f"Config file not found: {config_path}")
        return {"window_hours": 24}
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {"window_hours": 24}


def check_manual_run_enabled():
    """Check if manual runs are enabled via environment flag."""
    allow_manual_run = os.getenv("ALLOW_MANUAL_RUN", "false").lower() == "true"
    if not allow_manual_run:
        raise HTTPException(
            status_code=403,
            detail="Manual pipeline runs are disabled. Set ALLOW_MANUAL_RUN=true to enable."
        )
    return True


@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return {"ok": True, "service": "ingestor"}


@app.get("/")
async def root():
    """Root endpoint with service information."""
    service_name = os.getenv("SERVICE_NAME", "ingestor")
    version = os.getenv("SERVICE_VERSION", "0.1.0")
    manual_run_enabled = os.getenv("ALLOW_MANUAL_RUN", "false").lower() == "true"
    
    return {
        "service": service_name,
        "version": version,
        "manual_run_enabled": manual_run_enabled,
        "endpoints": {
            "health": "/healthz",
            "run_ingestion": "/run (POST)" if manual_run_enabled else "/run (disabled)"
        }
    }


@app.post("/run", response_model=RunIngestResponse)
async def run_ingestion(
    window_hours: Optional[int] = None,
    _: bool = Depends(check_manual_run_enabled)
):
    """
    Trigger RSS ingestion pipeline manually.
    
    Protected by ALLOW_MANUAL_RUN environment variable.
    Uses window_hours from YAML config if not specified.
    """
    try:
        # Load config to get default window_hours
        config = load_config()
        if window_hours is None:
            window_hours = config.get("window_hours", 24)
        
        logger.info(
            f"Starting manual RSS ingestion",
            extra={
                "window_hours": window_hours,
                "endpoint": "/run"
            }
        )
        
        # Run the ingestion pipeline
        stats = await run_ingest(window_hours=window_hours)
        
        # Determine status based on results
        status = "success"
        if stats.get("sources_error", 0) > 0:
            status = "partial_success"
        if stats.get("sources_ok", 0) == 0 and stats.get("sources_error", 0) > 0:
            status = "error"
        
        # Create success message
        message = (
            f"Ingestion completed in {stats['runtime_seconds']}s: "
            f"{stats['sources_ok']} sources OK, "
            f"{stats['items_inserted']}/{stats['items_total']} items inserted"
        )
        
        if stats.get("errors"):
            message += f", {len(stats['errors'])} errors"
        
        logger.info(
            "Manual ingestion completed",
            extra={
                "status": status,
                "sources_ok": stats.get("sources_ok", 0),
                "items_inserted": stats.get("items_inserted", 0),
                "runtime_seconds": stats.get("runtime_seconds", 0)
            }
        )
        
        return RunIngestResponse(
            status=status,
            message=message,
            stats=stats
        )
        
    except Exception as e:
        logger.error(
            f"Manual ingestion failed: {e}",
            extra={"endpoint": "/run", "window_hours": window_hours}
        )
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion pipeline failed: {str(e)}"
        )


@app.get("/config")
async def get_config():
    """Get current configuration (for debugging)."""
    config = load_config()
    return {
        "config": config,
        "manual_run_enabled": os.getenv("ALLOW_MANUAL_RUN", "false").lower() == "true"
    }


@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    manual_run_enabled = os.getenv("ALLOW_MANUAL_RUN", "false").lower() == "true"
    
    logger.info(
        "Starting ingestor service",
        extra={
            "service": "ingestor",
            "version": "0.1.0",
            "manual_run_enabled": manual_run_enabled
        }
    )


if __name__ == "__main__":
    logger.info("Starting ingestor service via uvicorn")
    uvicorn.run(
        "newsbot.ingestor.app:app",
        host=settings.service_host,
        port=settings.service_port or 8001,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )