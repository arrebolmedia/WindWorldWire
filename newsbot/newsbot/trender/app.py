"""Trender service FastAPI application."""

import os
import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List

from newsbot.core.settings import settings
from newsbot.core.logging import setup_logging, get_logger

# Setup logging
setup_logging("trender")
logger = get_logger(__name__)

app = FastAPI(title="NewsBot Trender", version="0.1.0")


class TrendRunResponse(BaseModel):
    """Response model for trend run."""
    status: str
    message: str
    stats: Dict[str, Any]
    trends: Optional[List[Dict[str, Any]]] = None


class TopicsRunResponse(BaseModel):
    """Response model for topics run."""
    status: str
    message: str
    stats: Dict[str, Any]
    topics: Optional[List[Dict[str, Any]]] = None


def check_manual_run_enabled():
    """Check if manual runs are enabled via environment flag."""
    allow_manual_run = os.getenv("ALLOW_MANUAL_RUN", "false").lower() == "true"
    if not allow_manual_run:
        raise HTTPException(
            status_code=403,
            detail="Manual runs are disabled. Set ALLOW_MANUAL_RUN=true to enable."
        )
    return True


@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return {"ok": True, "service": "trender"}


@app.get("/")
async def root():
    """Root endpoint."""
    service_name = os.getenv("SERVICE_NAME", "trender")
    version = os.getenv("SERVICE_VERSION", "0.1.0")
    manual_run_enabled = os.getenv("ALLOW_MANUAL_RUN", "false").lower() == "true"
    
    return {
        "service": service_name, 
        "version": version,
        "endpoints": {
            "health": "/healthz",
            "trend_run": "/trend/run (POST)" if manual_run_enabled else "/trend/run (disabled)",
            "topics_run": "/topics/run (POST)" if manual_run_enabled else "/topics/run (disabled)"
        }
    }


@app.post("/trend/run", response_model=TrendRunResponse)
async def run_trending(
    window_hours: Optional[int] = 24,
    top_k: Optional[int] = 50,
    _: bool = Depends(check_manual_run_enabled)
):
    """
    Trigger trending analysis pipeline manually.
    
    Runs complete trending pipeline:
    1. Cluster recent content using embeddings
    2. Score clusters based on multiple metrics
    3. Select top-K trending topics globally
    
    Protected by ALLOW_MANUAL_RUN environment variable.
    """
    try:
        from newsbot.trender.pipeline import run_trending_pipeline
        
        logger.info(
            f"Starting manual trending analysis",
            extra={
                "window_hours": window_hours,
                "top_k": top_k,
                "endpoint": "/trend/run"
            }
        )
        
        # Run the trending pipeline
        results = await run_trending_pipeline(
            window_hours=window_hours,
            top_k=top_k
        )
        
        # Determine status based on results
        status = "success"
        clusters_found = results.get("clusters_created", 0)
        trends_selected = results.get("trends_selected", 0)
        
        if clusters_found == 0:
            status = "no_data"
        elif trends_selected == 0:
            status = "no_trends"
        
        # Create message
        message = (
            f"Trending analysis completed in {results['runtime_seconds']:.2f}s: "
            f"{clusters_found} clusters created, "
            f"{trends_selected}/{top_k} trends selected"
        )
        
        return TrendRunResponse(
            status=status,
            message=message,
            stats=results,
            trends=results.get("selected_trends", [])
        )
        
    except Exception as e:
        logger.error(f"Trending analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Trending analysis failed: {str(e)}")


@app.post("/topics/run", response_model=TopicsRunResponse)
async def run_topics_analysis(
    topic_name: Optional[str] = None,
    window_hours: Optional[int] = 24,
    top_k: Optional[int] = 20,
    _: bool = Depends(check_manual_run_enabled)
):
    """
    Trigger topic-specific analysis manually.
    
    Runs topic-focused trending pipeline:
    1. Filter content by topic queries/keywords
    2. Cluster topic-specific content
    3. Score and select top-K for the topic
    
    Protected by ALLOW_MANUAL_RUN environment variable.
    """
    try:
        from newsbot.trender.topics import run_topics_pipeline
        
        logger.info(
            f"Starting topic analysis",
            extra={
                "topic_name": topic_name,
                "window_hours": window_hours,
                "top_k": top_k,
                "endpoint": "/topics/run"
            }
        )
        
        # Run the topics pipeline
        results = await run_topics_pipeline(
            topic_name=topic_name,
            window_hours=window_hours,
            top_k=top_k
        )
        
        # Determine status based on results
        status = "success"
        topics_processed = results.get("topics_processed", 0)
        content_analyzed = results.get("content_analyzed", 0)
        
        if topics_processed == 0:
            status = "no_topics"
        elif content_analyzed == 0:
            status = "no_content"
        
        # Create message
        message = (
            f"Topic analysis completed in {results['runtime_seconds']:.2f}s: "
            f"{topics_processed} topics processed, "
            f"{content_analyzed} items analyzed"
        )
        
        return TopicsRunResponse(
            status=status,
            message=message,
            stats=results,
            topics=results.get("topic_results", [])
        )
        
    except Exception as e:
        logger.error(f"Topic analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Topic analysis failed: {str(e)}")


@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    logger.info("Starting trender service", extra={"service": "trender", "version": "0.1.0"})


if __name__ == "__main__":
    logger.info("Starting trender service via uvicorn")
    uvicorn.run(
        "newsbot.trender.app:app",
        host=settings.service_host,
        port=settings.service_port or 8002,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )