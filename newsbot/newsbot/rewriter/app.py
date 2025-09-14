"""
FastAPI application for the article rewriter service.

Provides REST API endpoints for converting clusters to publication-ready articles
with comprehensive validation and multiple output formats.
"""

import asyncio
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, validator

from newsbot.core.logging import get_logger, setup_logging
from newsbot.core.settings import settings
from .seo_rewriter import SEOArticleRewriter, rewrite_cluster_quick, rewrite_cluster_comprehensive
from .template_renderer import TemplateRenderer, render_article_html, render_article_preview
from .validators import validate_complete_article, ValidationResult
from .models import DraftArticle

# Setup logging
setup_logging("rewriter")
logger = get_logger(__name__)

# FastAPI app initialization
app = FastAPI(
    title="Article Rewriter API",
    description="Convert news clusters to SEO-optimized publication-ready articles",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global rewriter instance
rewriter_instance = None
template_renderer = TemplateRenderer()


# Request/Response Models
class SourceData(BaseModel):
    """Source data for article generation."""
    url: str = Field(..., description="Source URL")
    title: str = Field("", description="Source title")
    summary: str = Field("", description="Source summary")
    content: str = Field("", description="Source content")
    published_date: Optional[str] = Field(None, description="Publication date")
    
    @validator('url')
    def validate_url(cls, v):
        if not v.startswith(('http://', 'https://')):
            raise ValueError('URL must start with http:// or https://')
        return v


class ClusterData(BaseModel):
    """Cluster data for rewriting."""
    topic: str = Field(..., description="Main topic of the cluster")
    summary: str = Field("", description="Cluster summary")
    sources: List[SourceData] = Field(..., min_items=1, description="Source articles")
    cluster_id: Optional[str] = Field(None, description="Unique cluster identifier")
    
    @validator('sources')
    def validate_sources(cls, v):
        if len(v) == 0:
            raise ValueError('At least one source is required')
        return v


class RewriteRequest(BaseModel):
    """Request for article rewriting."""
    cluster: ClusterData = Field(..., description="Cluster data to rewrite")
    language: str = Field("es", description="Target language (es/en)")
    quality_mode: str = Field("balanced", description="Quality mode: quick/balanced/comprehensive")
    output_format: str = Field("json", description="Output format: json/html/preview/wordpress")
    
    @validator('language')
    def validate_language(cls, v):
        if v not in ['es', 'en']:
            raise ValueError('Language must be "es" or "en"')
        return v
    
    @validator('quality_mode')
    def validate_quality_mode(cls, v):
        if v not in ['quick', 'balanced', 'comprehensive']:
            raise ValueError('Quality mode must be quick/balanced/comprehensive')
        return v
    
    @validator('output_format')
    def validate_output_format(cls, v):
        if v not in ['json', 'html', 'preview', 'wordpress', 'amp']:
            raise ValueError('Output format must be json/html/preview/wordpress/amp')
        return v


class RewriteResponse(BaseModel):
    """Response from article rewriting."""
    success: bool = Field(..., description="Whether rewriting succeeded")
    article: Optional[Dict[str, Any]] = Field(None, description="Generated article data")
    validation_results: Optional[Dict[str, Any]] = Field(None, description="Validation feedback")
    processing_time: float = Field(..., description="Processing time in seconds")
    quality_score: float = Field(..., description="Overall quality score (0-100)")
    warnings: List[str] = Field(default_factory=list, description="Processing warnings")
    error: Optional[str] = Field(None, description="Error message if failed")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(..., description="Check timestamp")
    version: str = Field(..., description="API version")
    components: Dict[str, str] = Field(..., description="Component status")


# Dependency to get rewriter instance
async def get_rewriter():
    """Get or create rewriter instance."""
    global rewriter_instance
    if rewriter_instance is None:
        rewriter_instance = SEOArticleRewriter()
    return rewriter_instance


# Health check endpoint
@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """
    Health check endpoint to verify service status.
    
    Returns current system status and component health.
    """
    try:
        # Check rewriter initialization
        rewriter = await get_rewriter()
        rewriter_status = "healthy" if rewriter else "error"
        
        # Check template renderer
        renderer_status = "healthy" if template_renderer else "error"
        
        # Overall status
        overall_status = "healthy" if all([
            rewriter_status == "healthy",
            renderer_status == "healthy"
        ]) else "degraded"
        
        return HealthResponse(
            status=overall_status,
            timestamp=datetime.now(timezone.utc),
            version="1.0.0",
            components={
                "rewriter": rewriter_status,
                "template_renderer": renderer_status,
                "llm_provider": type(rewriter.llm_provider).__name__ if rewriter else "unknown"
            }
        )
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return HealthResponse(
            status="error",
            timestamp=datetime.now(timezone.utc),
            version="1.0.0",
            components={
                "error": str(e)
            }
        )


# Legacy health check endpoint
@app.get("/healthz", tags=["System"])
async def health_check_legacy():
    """Legacy health check endpoint."""
    return {"ok": True, "service": "rewriter"}


# Root endpoint
@app.get("/", tags=["System"])
async def root():
    """Root endpoint with API information."""
    return {
        "message": "Article Rewriter API",
        "version": "1.0.0",
        "service": "rewriter",
        "description": "Convert news clusters to SEO-optimized publication-ready articles",
        "endpoints": {
            "health": "/health",
            "docs": "/docs",
            "rewrite": "/rewrite",
            "preview": "/rewrite/preview",
            "mock_data": "/rewrite/mock-data",
            "validate": "/validate",
            "stats": "/stats"
        }
    }


# Mock data endpoint for testing
@app.get("/rewrite/mock-data", tags=["Testing"])
async def get_mock_cluster_data():
    """
    Get mock cluster data for testing the rewriter.
    
    Returns sample cluster data that can be used for testing.
    """
    mock_data = {
        "topic": "Energía Renovable en España",
        "summary": "Nuevos desarrollos en el sector de energía renovable en España muestran crecimiento significativo.",
        "sources": [
            {
                "url": "https://example.com/energia-renovable-1",
                "title": "España instala 1,200 MW de energía solar en primer trimestre",
                "summary": "El sector solar español experimentó un crecimiento récord con la instalación de 1,200 MW de nueva capacidad en los primeros tres meses del año.",
                "content": "El sector de energía solar en España ha mostrado un crecimiento excepcional durante el primer trimestre del año. Según datos del Ministerio de Transición Ecológica, se instalaron 1,200 MW de nueva capacidad solar fotovoltaica. Este crecimiento representa un incremento del 30% comparado con el mismo período del año anterior. Las comunidades autónomas que lideraron las instalaciones fueron Andalucía, Castilla-La Mancha y Extremadura.",
                "published_date": "2024-01-15"
            },
            {
                "url": "https://example.com/energia-renovable-2", 
                "title": "Inversión en eólica marina alcanza récord histórico",
                "summary": "La inversión en proyectos de energía eólica marina en España alcanzó 2,500 millones de euros, estableciendo un nuevo récord.",
                "content": "La energía eólica marina en España ha atraído inversiones por valor de 2,500 millones de euros en 2024, marcando un hito histórico para el sector. Los proyectos se concentran principalmente en las costas de Galicia, Asturias y País Vasco. Se espera que estos proyectos generen más de 3,000 empleos directos y contribuyan significativamente a los objetivos de descarbonización del país para 2030.",
                "published_date": "2024-01-20"
            },
            {
                "url": "https://example.com/energia-renovable-3",
                "title": "Plan Nacional de Energía establece nuevas metas",
                "summary": "El gobierno español actualiza el Plan Nacional Integrado de Energía y Clima con metas más ambiciosas para 2030.",
                "content": "El Gobierno de España ha presentado la actualización del Plan Nacional Integrado de Energía y Clima (PNIEC) 2021-2030, estableciendo objetivos más ambiciosos para la transición energética. El plan contempla alcanzar el 42% de energías renovables en el consumo final de energía para 2030, superando el objetivo anterior del 40%. Se prevé una inversión total de 18,000 millones de euros en el período.",
                "published_date": "2024-01-25"
            }
        ],
        "cluster_id": "renewable_energy_spain_2024_01"
    }
    
    return {"mock_cluster": mock_data}


# Main rewriting endpoint
@app.post("/rewrite", response_model=RewriteResponse, tags=["Rewriting"])
async def rewrite_article(
    request: RewriteRequest,
    background_tasks: BackgroundTasks,
    rewriter: SEOArticleRewriter = Depends(get_rewriter)
):
    """
    Convert a news cluster to a publication-ready article.
    
    Takes cluster data and generates an SEO-optimized article with validation.
    Supports multiple quality modes and output formats.
    """
    start_time = datetime.now()
    
    try:
        # Convert Pydantic models to dict
        cluster_data = request.cluster.dict()
        
        # Choose rewriting strategy based on quality mode
        if request.quality_mode == "quick":
            article = await rewrite_cluster_quick(cluster_data, request.language)
            validation_results = {}
            
        elif request.quality_mode == "comprehensive":
            article, validation_results = await rewrite_cluster_comprehensive(
                cluster_data, 
                request.language,
                max_iterations=3,
                min_quality_score=85.0
            )
            
        else:  # balanced
            article, validation_results = await rewriter.rewrite_cluster_to_article(
                cluster_data, 
                request.language
            )
        
        # Calculate processing time
        processing_time = (datetime.now() - start_time).total_seconds()
        
        # Calculate quality score
        quality_score = 100.0  # Default for quick mode
        warnings = []
        
        if validation_results:
            scores = [result.score for result in validation_results.values()]
            quality_score = sum(scores) / len(scores) if scores else 0.0
            
            # Collect warnings
            for category, result in validation_results.items():
                warnings.extend([f"[{category.upper()}] {warning}" for warning in result.warnings[:2]])
        
        # Format output based on requested format
        if request.output_format == "html":
            output_content = render_article_html(article, "default")
            
        elif request.output_format == "preview":
            output_content = render_article_preview(article)
            
        elif request.output_format == "wordpress":
            output_content = render_article_html(article, "wordpress")
            
        elif request.output_format == "amp":
            output_content = render_article_html(article, "amp")
            
        else:  # json
            output_content = article.dict()
        
        # Log successful completion
        logger.info(f"Article rewritten successfully: '{article.title}' (score: {quality_score:.1f}, time: {processing_time:.2f}s)")
        
        response = RewriteResponse(
            success=True,
            article=output_content if isinstance(output_content, dict) else {"html": output_content},
            validation_results={k: v.to_dict() for k, v in validation_results.items()} if validation_results else None,
            processing_time=processing_time,
            quality_score=quality_score,
            warnings=warnings[:5]  # Limit warnings
        )
        
        return response
        
    except Exception as e:
        processing_time = (datetime.now() - start_time).total_seconds()
        error_msg = str(e)
        
        logger.error(f"Rewriting failed: {error_msg}")
        
        return RewriteResponse(
            success=False,
            processing_time=processing_time,
            quality_score=0.0,
            error=error_msg
        )


# HTML preview endpoint
@app.post("/rewrite/preview", response_class=HTMLResponse, tags=["Rewriting"])
async def rewrite_article_preview(
    request: RewriteRequest,
    rewriter: SEOArticleRewriter = Depends(get_rewriter)
):
    """
    Generate article and return HTML preview.
    
    Quick endpoint for previewing generated articles in HTML format.
    """
    try:
        cluster_data = request.cluster.dict()
        
        # Use quick mode for preview
        article = await rewrite_cluster_quick(cluster_data, request.language)
        
        # Render as preview HTML
        html_content = render_article_preview(article)
        
        # Wrap in basic HTML document
        full_html = f"""
        <!DOCTYPE html>
        <html lang="{request.language}">
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Vista Previa - {article.title}</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }}
                .article-preview {{ border: 1px solid #ddd; padding: 20px; border-radius: 5px; }}
                .meta-description {{ color: #666; font-style: italic; margin-bottom: 20px; }}
                .lead {{ font-size: 1.1em; font-weight: 500; }}
                .section-preview {{ margin: 15px 0; padding: 10px; background: #f9f9f9; }}
                .metadata {{ margin-top: 30px; padding: 15px; background: #e9ecef; font-size: 0.9em; }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        
        return HTMLResponse(content=full_html)
        
    except Exception as e:
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Error</title></head>
        <body>
            <h1>Error generando vista previa</h1>
            <p>{str(e)}</p>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html, status_code=500)


# Legacy mock endpoint (for compatibility)
@app.post("/rewrite/mock", tags=["Testing"])
async def rewrite_mock():
    """Mock rewrite endpoint for testing (legacy)."""
    return {
        "status": "success",
        "message": "Use /rewrite with mock data from /rewrite/mock-data",
        "article": {
            "title": "Sample Article Title",
            "content": "Sample article content",
            "meta_description": "Sample meta description"
        },
        "redirect": {
            "mock_data": "/rewrite/mock-data",
            "rewrite": "/rewrite",
            "preview": "/rewrite/preview"
        }
    }


# Validation endpoint
@app.post("/validate", tags=["Validation"])
async def validate_article_content(
    article_data: Dict[str, Any],
    source_data: List[Dict[str, Any]]
):
    """
    Validate article content against sources and SEO standards.
    
    Provides detailed validation feedback without rewriting.
    """
    try:
        # Parse article data
        article = DraftArticle(**article_data)
        
        # Run validation
        validation_results = validate_complete_article(
            article=article,
            source_data=source_data,
            strict_hallucination_check=True
        )
        
        # Calculate overall score
        scores = [result.score for result in validation_results.values()]
        overall_score = sum(scores) / len(scores) if scores else 0.0
        
        return {
            "success": True,
            "overall_score": overall_score,
            "validation_results": {k: v.to_dict() for k, v in validation_results.items()},
            "recommendations": [
                error for result in validation_results.values() 
                for error in result.errors[:2]
            ]
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# Statistics endpoint
@app.get("/stats", tags=["System"])
async def get_service_stats():
    """
    Get service statistics and performance metrics.
    
    Returns usage statistics and system performance data.
    """
    try:
        rewriter = await get_rewriter()
        
        stats = {
            "service": "Article Rewriter API",
            "version": "1.0.0",
            "uptime": "Available",  # Would implement actual uptime tracking
            "llm_provider": type(rewriter.llm_provider).__name__,
            "supported_languages": ["es", "en"],
            "supported_formats": ["json", "html", "preview", "wordpress", "amp"],
            "quality_modes": ["quick", "balanced", "comprehensive"],
            "features": {
                "anti_hallucination": True,
                "seo_optimization": True,
                "multiple_sources": True,
                "structured_output": True,
                "validation": True
            }
        }
        
        return stats
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Startup event
@app.on_event("startup")
async def startup_event():
    """Startup event handler."""
    logger.info("Starting rewriter service", extra={"service": "rewriter", "version": "1.0.0"})


# Error handlers
@app.exception_handler(ValueError)
async def value_error_handler(request, exc):
    """Handle validation errors."""
    return JSONResponse(
        status_code=400,
        content={"error": "Validation error", "detail": str(exc)}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": "An unexpected error occurred"}
    )


# Run server
def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = False):
    """
    Run the FastAPI server.
    
    Args:
        host: Host address
        port: Port number
        reload: Enable auto-reload for development
    """
    uvicorn.run(
        "newsbot.rewriter.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info"
    )


if __name__ == "__main__":
    logger.info("Starting rewriter service via uvicorn")
    uvicorn.run(
        "newsbot.rewriter.app:app",
        host=settings.service_host,
        port=settings.service_port or 8003,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )