"""
NewsBot Article Rewriter Module

Converts news clusters to SEO-optimized publication-ready articles with comprehensive
validation and anti-hallucination checks.

Main Components:
- models: Pydantic models for structured articles
- llm_provider: LLM abstraction with fallback providers
- validators: Anti-hallucination and SEO compliance validation
- seo_rewriter: Main rewriter orchestration logic
- template_renderer: HTML generation for multiple formats
- app: FastAPI application with REST endpoints

Key Features:
- Zero-hallucination validation against source materials
- SEO optimization with technical compliance checking
- Multiple output formats (HTML, WordPress, AMP, JSON)
- Comprehensive quality scoring and iterative improvement
- Source attribution and credibility verification
"""

from .models import DraftArticle, ArticleSection, FAQ, SourceLink, JSONLDNewsArticle
from .llm_provider import LLMProvider, DummyLLMProvider, LLMProviderFactory
from .validators import validate_complete_article, ValidationResult
from .seo_rewriter import SEOArticleRewriter, rewrite_cluster_quick, rewrite_cluster_comprehensive
from .template_renderer import TemplateRenderer, render_article_html, render_article_preview

__version__ = "1.0.0"
__author__ = "Wind World Wire"

# Main exports
__all__ = [
    # Models
    "DraftArticle",
    "ArticleSection", 
    "FAQ",
    "SourceLink",
    "JSONLDNewsArticle",
    
    # LLM Providers
    "LLMProvider",
    "DummyLLMProvider", 
    "LLMProviderFactory",
    
    # Validation
    "validate_complete_article",
    "ValidationResult",
    
    # Rewriting
    "SEOArticleRewriter",
    "rewrite_cluster_quick",
    "rewrite_cluster_comprehensive",
    
    # Template Rendering
    "TemplateRenderer",
    "render_article_html",
    "render_article_preview",
]