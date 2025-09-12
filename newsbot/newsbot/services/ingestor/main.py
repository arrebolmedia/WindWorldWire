"""Ingestor service - Ingests news from various sources."""
import uvicorn
from fastapi import FastAPI

from newsbot.services.base import create_app


app = create_app("ingestor")


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "NewsBot Ingestor Service", "version": "0.1.0"}


# TODO: Add endpoints for:
# - POST /sources/{source_id}/ingest - Trigger manual ingestion
# - GET /sources - List configured sources
# - GET /ingestion/status - Get ingestion status
# - POST /ingestion/start - Start ingestion process
# - POST /ingestion/stop - Stop ingestion process


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info",
    )