"""Trender service - Analyzes trending topics and stories."""
import uvicorn
from fastapi import FastAPI

from newsbot.services.base import create_app


app = create_app("trender")


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "NewsBot Trender Service", "version": "0.1.0"}


# TODO: Add endpoints for:
# - GET /trends/topics - Get trending topics
# - GET /trends/articles - Get trending articles
# - POST /trends/analyze - Trigger trend analysis
# - GET /trends/scores/{article_id} - Get trend scores for article
# - GET /analytics/engagement - Get engagement analytics


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level="info",
    )