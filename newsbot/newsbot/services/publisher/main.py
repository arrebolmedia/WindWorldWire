"""Publisher service - Publishes content to various platforms."""
import uvicorn
from fastapi import FastAPI

from newsbot.services.base import create_app


app = create_app("publisher")


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "NewsBot Publisher Service", "version": "0.1.0"}


# TODO: Add endpoints for:
# - POST /publish/article - Publish article to platform
# - GET /publish/jobs - List publishing jobs
# - POST /publish/schedule - Schedule article for publishing
# - DELETE /publish/jobs/{job_id} - Cancel publishing job
# - GET /platforms - List supported publishing platforms


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8005,
        reload=True,
        log_level="info",
    )