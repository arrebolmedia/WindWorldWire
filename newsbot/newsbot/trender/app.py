"""Trender service FastAPI application."""

import os
import uvicorn
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import secrets

from newsbot.core.settings import settings
from newsbot.core.logging import setup_logging, get_logger

# Setup logging
setup_logging("trender")
logger = get_logger(__name__)

app = FastAPI(title="NewsBot Trender", version="0.1.0", description="Trending topics analysis API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure as needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Basic auth setup
security = HTTPBasic()


class TrendRunRequest(BaseModel):
    """Request model for trend run."""
    window_hours: int = Field(default=3, ge=1, le=168, description="Time window in hours")
    k_global: int = Field(default=5, ge=1, le=100, description="Number of global picks")


class TopicsRunRequest(BaseModel):
    """Request model for topics run."""
    window_hours: int = Field(default=3, ge=1, le=168, description="Time window in hours")


class SelectedPickInfo(BaseModel):
    """Model for selected pick information."""
    cluster_id: int
    composite_score: float
    final_score: float
    selection_type: str
    topic_key: Optional[str] = None
    topic_priority: Optional[float] = None
    rank: Optional[int] = None


class TrendRunResponse(BaseModel):
    """Response model for trend run."""
    status: str
    message: str
    counts: Dict[str, int]
    selection: Optional[Dict[str, Any]] = None


class TopicsRunResponse(BaseModel):
    """Response model for topics run."""
    status: str
    message: str
    counts: Dict[str, int]
    topics: Dict[str, Dict[str, Any]]


def get_current_username(credentials: HTTPBasicCredentials = Depends(security)):
    """Verify basic auth credentials if auth is enabled."""
    auth_enabled = os.getenv("TRENDER_AUTH_ENABLED", "false").lower() == "true"
    
    if not auth_enabled:
        return None  # Auth disabled
    
    # Get credentials from environment
    correct_username = os.getenv("TRENDER_USERNAME", "admin")
    correct_password = os.getenv("TRENDER_PASSWORD", "secret")
    
    is_correct_username = secrets.compare_digest(credentials.username, correct_username)
    is_correct_password = secrets.compare_digest(credentials.password, correct_password)
    
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def check_manual_run_enabled():
    """Check if manual runs are enabled via environment flag."""
    allow_manual_run = os.getenv("ALLOW_MANUAL_RUN", "true").lower() == "true"  # Default to true for testing
    if not allow_manual_run:
        raise HTTPException(
            status_code=403,
            detail="Manual runs are disabled. Set ALLOW_MANUAL_RUN=true to enable."
        )
    return True


@app.get("/healthz")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "trender"}


@app.get("/")
async def root():
    """Root endpoint."""
    service_name = os.getenv("SERVICE_NAME", "trender")
    version = os.getenv("SERVICE_VERSION", "0.1.0")
    manual_run_enabled = os.getenv("ALLOW_MANUAL_RUN", "true").lower() == "true"
    auth_enabled = os.getenv("TRENDER_AUTH_ENABLED", "false").lower() == "true"
    
    return {
        "service": service_name, 
        "version": version,
        "auth_enabled": auth_enabled,
        "endpoints": {
            "health": "/healthz",
            "trend_run": "/trend/run (POST)" if manual_run_enabled else "/trend/run (disabled)",
            "topics_run": "/topics/run (POST)" if manual_run_enabled else "/topics/run (disabled)"
        }
    }


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
async def run_trending_endpoint(
    request: TrendRunRequest,
    _: bool = Depends(check_manual_run_enabled),
    username: Optional[str] = Depends(get_current_username)
):
    """
    Run global trending analysis pipeline.
    
    Coordinates the complete trending pipeline:
    1. Load recent items from database
    2. Cluster similar content using embeddings
    3. Score clusters based on multiple metrics
    4. Select top-K trending topics globally and per-topic
    
    Returns structured selection with global picks and topic picks.
    """
    try:
        from newsbot.trender.pipeline import run_trending
        
        logger.info(
            f"Starting trending analysis via API",
            extra={
                "window_hours": request.window_hours,
                "k_global": request.k_global,
                "user": username,
                "endpoint": "/trend/run"
            }
        )
        
        # Run the new pipeline orchestrator
        selection = await run_trending(
            window_hours=request.window_hours,
            k_global=request.k_global
        )
        
        # Extract counts and status
        global_count = len(selection.global_picks)
        topic_count = len(selection.topic_picks)
        total_count = selection.total_picks
        
        # Determine status
        if total_count == 0:
            status = "no_results"
            message = f"No trending topics found in the last {request.window_hours} hours"
        else:
            status = "success"
            message = f"Found {total_count} trending picks ({global_count} global, {topic_count} topic-specific)"
        
        # Format selection for response
        selection_data = {
            "global_picks": [
                {
                    "cluster_id": pick.cluster_id,
                    "composite_score": pick.composite_score,
                    "final_score": pick.final_score,
                    "selection_type": pick.selection_type,
                    "rank": pick.rank
                }
                for pick in selection.global_picks
            ],
            "topic_picks": [
                {
                    "cluster_id": pick.cluster_id,
                    "composite_score": pick.composite_score,
                    "final_score": pick.final_score,
                    "selection_type": pick.selection_type,
                    "topic_key": pick.topic_key,
                    "topic_priority": pick.topic_priority,
                    "rank": pick.rank
                }
                for pick in selection.topic_picks
            ],
            "total_picks": total_count
        }
        
        return TrendRunResponse(
            status=status,
            message=message,
            counts={
                "global_picks": global_count,
                "topic_picks": topic_count,
                "total_picks": total_count
            },
            selection=selection_data
        )
        
    except Exception as e:
        logger.error(f"Trending analysis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Trending analysis failed: {str(e)}"
        )


@app.post("/topics/run", response_model=TopicsRunResponse)
async def run_topics_endpoint(
    request: TopicsRunRequest,
    _: bool = Depends(check_manual_run_enabled),
    username: Optional[str] = Depends(get_current_username)
):
    """
    Run per-topic trending analysis.
    
    Runs topic-focused trending pipeline:
    1. Load topics configuration from YAML
    2. For each enabled topic:
       - Filter content by topic queries/keywords
       - Cluster topic-specific content
       - Score and select trending picks for the topic
    
    Returns selections per topic with counts and details.
    """
    try:
        from newsbot.trender.pipeline import run_topics
        
        logger.info(
            f"Starting topics analysis via API",
            extra={
                "window_hours": request.window_hours,
                "user": username,
                "endpoint": "/topics/run"
            }
        )
        
        # Run the new topics pipeline orchestrator
        topics_results = await run_topics(window_hours=request.window_hours)
        
        # Calculate overall counts
        total_topics = len(topics_results)
        total_picks = sum(selection.total_picks for selection in topics_results.values())
        
        # Determine status
        if total_topics == 0:
            status = "no_topics"
            message = "No enabled topics found in configuration"
        elif total_picks == 0:
            status = "no_results"
            message = f"No trending picks found across {total_topics} topics in the last {request.window_hours} hours"
        else:
            status = "success"
            message = f"Found {total_picks} trending picks across {total_topics} topics"
        
        # Format topics results for response
        topics_data = {}
        for topic_key, selection in topics_results.items():
            topics_data[topic_key] = {
                "global_picks": [
                    {
                        "cluster_id": pick.cluster_id,
                        "composite_score": pick.composite_score,
                        "final_score": pick.final_score,
                        "selection_type": pick.selection_type,
                        "rank": pick.rank
                    }
                    for pick in selection.global_picks
                ],
                "topic_picks": [
                    {
                        "cluster_id": pick.cluster_id,
                        "composite_score": pick.composite_score,
                        "final_score": pick.final_score,
                        "selection_type": pick.selection_type,
                        "topic_key": pick.topic_key,
                        "topic_priority": pick.topic_priority,
                        "rank": pick.rank
                    }
                    for pick in selection.topic_picks
                ],
                "total_picks": selection.total_picks,
                "counts": {
                    "global_picks": len(selection.global_picks),
                    "topic_picks": len(selection.topic_picks)
                }
            }
        
        return TopicsRunResponse(
            status=status,
            message=message,
            counts={
                "total_topics": total_topics,
                "total_picks": total_picks,
                "topics_with_picks": sum(1 for sel in topics_results.values() if sel.total_picks > 0)
            },
            topics=topics_data
        )
        
    except Exception as e:
        logger.error(f"Topics analysis failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Topics analysis failed: {str(e)}"
        )


@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    auth_enabled = os.getenv("TRENDER_AUTH_ENABLED", "false").lower() == "true"
    manual_runs_enabled = os.getenv("ALLOW_MANUAL_RUN", "true").lower() == "true"
    
    logger.info(
        "Starting trender service",
        extra={
            "service": "trender",
            "version": "0.1.0",
            "auth_enabled": auth_enabled,
            "manual_runs_enabled": manual_runs_enabled
        }
    )


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler."""
    logger.info("Shutting down trender service")


if __name__ == "__main__":
    logger.info("Starting trender service via uvicorn")
    uvicorn.run(
        "newsbot.trender.app:app",
        host=settings.service_host,
        port=settings.service_port or 8002,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )