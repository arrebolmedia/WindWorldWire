"""Rewriter service - Rewrites and localizes content."""
import uvicorn
from fastapi import FastAPI

from newsbot.services.base import create_app


app = create_app("rewriter")


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "NewsBot Rewriter Service", "version": "0.1.0"}


# TODO: Add endpoints for:
# - POST /rewrite/summarize - Summarize article content
# - POST /rewrite/translate - Translate article to different language
# - POST /rewrite/localize - Localize content for Mexican audience
# - GET /rewrites/{article_id} - Get all rewrites for an article
# - POST /rewrites/{rewrite_id}/approve - Approve a rewrite


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8003,
        reload=True,
        log_level="info",
    )