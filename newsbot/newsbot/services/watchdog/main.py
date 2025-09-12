"""Watchdog service - Monitors system health and performance."""
import uvicorn
from fastapi import FastAPI

from newsbot.services.base import create_app


app = create_app("watchdog")


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "NewsBot Watchdog Service", "version": "0.1.0"}


# TODO: Add endpoints for:
# - GET /health/system - Overall system health
# - GET /health/services - Health of all services
# - GET /metrics/performance - Performance metrics
# - GET /alerts - Active alerts
# - POST /alerts/acknowledge - Acknowledge alerts


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8006,
        reload=True,
        log_level="info",
    )