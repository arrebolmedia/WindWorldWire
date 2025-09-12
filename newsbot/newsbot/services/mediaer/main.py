"""Mediaer service - Processes and optimizes media content."""
import uvicorn
from fastapi import FastAPI

from newsbot.services.base import create_app


app = create_app("mediaer")


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "NewsBot Mediaer Service", "version": "0.1.0"}


# TODO: Add endpoints for:
# - POST /media/process - Process media items
# - GET /media/{media_id} - Get media item details
# - POST /media/optimize - Optimize images/videos
# - POST /media/extract-text - Extract text from images (OCR)
# - GET /media/status/{job_id} - Get processing status


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8004,
        reload=True,
        log_level="info",
    )