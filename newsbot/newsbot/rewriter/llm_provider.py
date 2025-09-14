"""
LLM Provider interface and implementations for article rewriting.

Provides abstraction over different LLM providers with fallback mechanisms.
Includes dummy/NoLLM provider for testing without API dependencies.
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

from newsbot.core.logging import get_logger
from .models import DraftArticle, Language, ArticleSection, FAQ, SourceLink, JSONLDNewsArticle

logger = get_logger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def generate_article(
        self,
        cluster_data: Dict[str, Any],
        prompt_template: str,
        lang: Language = Language.SPANISH,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate article content from cluster data.
        
        Args:
            cluster_data: Cluster information and source items
            prompt_template: Template with variables for generation
            lang: Target language for generation
            **kwargs: Additional generation parameters
            
        Returns:
            Dict containing article components or error information
        """
        pass
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Check provider health and availability."""
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Provider identification name."""
        pass


class DummyLLMProvider(LLMProvider):
    """
    Dummy LLM provider for testing and fallback.
    
    Generates realistic article content without external API calls.
    Useful for development, testing, and when LLM services are unavailable.
    """
    
    def __init__(self):
        self.call_count = 0
        self.total_processing_time = 0.0
    
    @property
    def provider_name(self) -> str:
        return "DummyLLM"
    
    async def health_check(self) -> Dict[str, Any]:
        """Always healthy for dummy provider."""
        return {
            "status": "healthy",
            "provider": self.provider_name,
            "calls_made": self.call_count,
            "avg_response_time": self.total_processing_time / max(self.call_count, 1),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def generate_article(
        self,
        cluster_data: Dict[str, Any],
        prompt_template: str,
        lang: Language = Language.SPANISH,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate realistic dummy article content."""
        start_time = time.time()
        self.call_count += 1
        
        try:
            # Simulate processing delay
            await asyncio.sleep(0.5)
            
            # Extract cluster information
            cluster_id = cluster_data.get('cluster_id', 1)
            topic_name = cluster_data.get('topic', 'Actualidad')
            items = cluster_data.get('items', [])
            
            # Generate article components
            article_data = self._generate_article_components(
                cluster_id=cluster_id,
                topic_name=topic_name,
                items=items,
                lang=lang,
                **kwargs
            )
            
            processing_time = time.time() - start_time
            self.total_processing_time += processing_time
            
            return {
                "success": True,
                "article_data": article_data,
                "processing_time": processing_time,
                "provider": self.provider_name,
                "sources_used": len(items)
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error in dummy LLM generation: {str(e)}")
            
            return {
                "success": False,
                "error": f"Dummy LLM error: {str(e)}",
                "processing_time": processing_time,
                "provider": self.provider_name
            }
    
    def _generate_article_components(
        self,
        cluster_id: int,
        topic_name: str,
        items: List[Dict[str, Any]],
        lang: Language,
        **kwargs
    ) -> Dict[str, Any]:
        """Generate realistic article components based on cluster data."""
        
        # Use first item as primary source, or create dummy if none
        primary_item = items[0] if items else {
            'title': 'Desarrollo importante en actualidad económica',
            'summary': 'Nuevos acontecimientos marcan tendencias en el sector.',
            'url': 'https://example.com/noticia',
            'domain': 'example.com',
            'published_at': datetime.utcnow().isoformat()
        }
        
        # Generate based on language
        if lang == Language.SPANISH:
            return self._generate_spanish_article(cluster_id, topic_name, items, primary_item)
        else:
            return self._generate_english_article(cluster_id, topic_name, items, primary_item)
    
    def _generate_spanish_article(
        self,
        cluster_id: int,
        topic_name: str,
        items: List[Dict[str, Any]],
        primary_item: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate Spanish article content."""
        
        # Create realistic title based on primary item
        base_title = primary_item.get('title', 'Actualidad Económica')
        title = f"Análisis: {base_title[:50]}..." if len(base_title) > 50 else f"Análisis: {base_title}"
        
        # Generate slug from title
        slug = self._create_slug(title)
        
        # Create lead paragraph
        lead = (
            f"Los últimos desarrollos en {topic_name.lower()} han capturado la atención del mercado. "
            f"Según múltiples fuentes especializadas, {primary_item.get('summary', 'los eventos recientes')[:100]}... "
            f"Este análisis examina las implicaciones y perspectivas para el sector."
        )
        
        # Generate key points
        key_points = [
            f"Desarrollos significativos reportados por {len(items)} fuentes especializadas",
            f"Impacto directo en el sector de {topic_name.lower()} y mercados relacionados",
            "Análisis de tendencias y perspectivas a corto plazo",
            "Reacciones del mercado y posicionamiento de los principales actores"
        ]
        
        # Generate sections
        sections = [
            {
                "heading": "Contexto y Antecedentes",
                "content": f"<p>El sector de {topic_name.lower()} ha experimentado cambios significativos en las últimas semanas. Las fuentes consultadas coinciden en que {primary_item.get('summary', 'los desarrollos actuales')} representan un punto de inflexión importante.</p><p>Los antecedentes de esta situación se remontan a las tendencias observadas en trimestres anteriores, donde ya se anticipaban movimientos de esta naturaleza.</p>",
                "source_urls": [item.get('url', 'https://example.com') for item in items[:2]]
            },
            {
                "heading": "Análisis de Impacto",
                "content": f"<p>El impacto de estos desarrollos se extiende más allá del sector inmediato. Los expertos señalan que las repercusiones podrían afectar a:</p><ul><li>Cadenas de suministro y distribución</li><li>Políticas regulatorias del sector</li><li>Expectativas de inversión a mediano plazo</li><li>Posicionamiento competitivo de los principales actores</li></ul>",
                "source_urls": [item.get('url', 'https://example.com') for item in items[1:3]]
            },
            {
                "heading": "Perspectivas y Proyecciones",
                "content": "<p>Mirando hacia adelante, los analistas identifican varios escenarios posibles. El consenso sugiere que la situación actual podría mantenerse estable en el corto plazo, aunque factores externos podrían introducir volatilidad adicional.</p><p>Las proyecciones para los próximos meses indican una necesidad de monitoreo constante y adaptación estratégica por parte de los actores del sector.</p>",
                "source_urls": [item.get('url', 'https://example.com') for item in items[-2:]]
            }
        ]
        
        # Generate FAQs
        faqs = [
            {
                "question": f"¿Cuáles son las principales implicaciones de estos desarrollos en {topic_name.lower()}?",
                "answer": "Las implicaciones incluyen cambios en la dinámica del mercado, nuevas oportunidades de inversión y la necesidad de adaptación estratégica por parte de los actores del sector.",
                "source_urls": [items[0].get('url', 'https://example.com')] if items else []
            },
            {
                "question": "¿Qué pueden esperar los inversores en el corto plazo?",
                "answer": "Los inversores deben esperar un período de ajuste y posible volatilidad, aunque las perspectivas a mediano plazo se mantienen estables según el análisis de expertos.",
                "source_urls": [items[-1].get('url', 'https://example.com')] if items else []
            }
        ]
        
        # Generate source links
        source_links = []
        for i, item in enumerate(items[:10]):  # Max 10 sources
            source_links.append({
                "url": item.get('url', f'https://example.com/source-{i}'),
                "title": item.get('title', f'Fuente {i+1}')[:100],
                "domain": item.get('domain', 'example.com'),
                "published_at": item.get('published_at')
            })
        
        # Ensure minimum 2 sources
        if len(source_links) < 2:
            source_links.extend([
                {
                    "url": "https://reuters.com/business/example",
                    "title": "Análisis del sector - Reuters",
                    "domain": "reuters.com",
                    "published_at": datetime.utcnow().isoformat()
                },
                {
                    "url": "https://bloomberg.com/markets/example", 
                    "title": "Perspectivas del mercado - Bloomberg",
                    "domain": "bloomberg.com",
                    "published_at": datetime.utcnow().isoformat()
                }
            ])
        
        # Generate meta description
        meta_description = f"Análisis completo de los desarrollos en {topic_name.lower()}. Examinamos el impacto, perspectivas y proyecciones según múltiples fuentes especializadas del sector."
        
        # Generate JSON-LD
        json_ld = {
            "type": "NewsArticle",
            "headline": title,
            "description": meta_description,
            "author": {"@type": "Organization", "name": "Wind World Wire"},
            "publisher": {"@type": "Organization", "name": "Wind World Wire"},
            "datePublished": datetime.utcnow().isoformat(),
            "dateModified": datetime.utcnow().isoformat(),
            "articleSection": topic_name,
            "wordCount": 800
        }
        
        return {
            "title": title,
            "lead": lead,
            "key_points": key_points,
            "sections": sections,
            "faqs": faqs,
            "meta_description": meta_description,
            "slug": slug,
            "json_ld": json_ld,
            "source_links": source_links,
            "image_alt": f"Ilustración sobre desarrollos en {topic_name.lower()}. Cortesía de Wind World Wire.",
            "lang": "es",
            "cluster_id": cluster_id,
            "topic_name": topic_name
        }
    
    def _generate_english_article(
        self,
        cluster_id: int,
        topic_name: str,
        items: List[Dict[str, Any]],
        primary_item: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate English article content."""
        
        # Create realistic title
        base_title = primary_item.get('title', 'Economic Development')
        title = f"Analysis: {base_title[:50]}..." if len(base_title) > 50 else f"Analysis: {base_title}"
        
        slug = self._create_slug(title)
        
        lead = (
            f"Recent developments in {topic_name.lower()} have caught market attention. "
            f"According to specialized sources, {primary_item.get('summary', 'recent events')[:100]}... "
            f"This analysis examines the implications and outlook for the sector."
        )
        
        key_points = [
            f"Significant developments reported by {len(items)} specialized sources",
            f"Direct impact on {topic_name.lower()} sector and related markets",
            "Analysis of trends and short-term perspectives",
            "Market reactions and positioning of key players"
        ]
        
        sections = [
            {
                "heading": "Context and Background",
                "content": f"<p>The {topic_name.lower()} sector has experienced significant changes in recent weeks. Consulted sources agree that {primary_item.get('summary', 'current developments')} represent an important turning point.</p><p>The background to this situation dates back to trends observed in previous quarters, where movements of this nature were already anticipated.</p>",
                "source_urls": [item.get('url', 'https://example.com') for item in items[:2]]
            },
            {
                "heading": "Impact Analysis", 
                "content": "<p>The impact of these developments extends beyond the immediate sector. Experts point out that repercussions could affect:</p><ul><li>Supply and distribution chains</li><li>Sector regulatory policies</li><li>Medium-term investment expectations</li><li>Competitive positioning of major players</li></ul>",
                "source_urls": [item.get('url', 'https://example.com') for item in items[1:3]]
            }
        ]
        
        return {
            "title": title,
            "lead": lead,
            "key_points": key_points,
            "sections": sections,
            "faqs": [],
            "meta_description": f"Complete analysis of developments in {topic_name.lower()}. We examine impact, perspectives and projections according to multiple specialized sources.",
            "slug": slug,
            "json_ld": {
                "type": "NewsArticle",
                "headline": title,
                "description": f"Analysis of {topic_name.lower()} sector developments",
                "datePublished": datetime.utcnow().isoformat(),
                "dateModified": datetime.utcnow().isoformat()
            },
            "source_links": source_links[:2] if 'source_links' in locals() else [],
            "image_alt": f"Illustration about {topic_name.lower()} developments. Courtesy of Wind World Wire.",
            "lang": "en",
            "cluster_id": cluster_id,
            "topic_name": topic_name
        }
    
    def _create_slug(self, title: str) -> str:
        """Create URL-safe slug from title."""
        import re
        import unicodedata
        
        # Normalize unicode and remove accents
        normalized = unicodedata.normalize('NFKD', title)
        ascii_only = normalized.encode('ascii', 'ignore').decode('ascii')
        
        # Convert to lowercase and replace spaces/punctuation with hyphens
        slug = re.sub(r'[^a-z0-9]+', '-', ascii_only.lower())
        
        # Remove leading/trailing hyphens and consecutive hyphens
        slug = re.sub(r'^-+|-+$', '', slug)
        slug = re.sub(r'-+', '-', slug)
        
        return slug[:80]  # Limit length


class NoLLMProvider(LLMProvider):
    """
    Minimal provider that returns error responses.
    
    Used when no LLM service is available or configured.
    """
    
    @property
    def provider_name(self) -> str:
        return "NoLLM"
    
    async def health_check(self) -> Dict[str, Any]:
        """Always returns unavailable status."""
        return {
            "status": "unavailable",
            "provider": self.provider_name,
            "message": "No LLM provider configured",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def generate_article(
        self,
        cluster_data: Dict[str, Any],
        prompt_template: str,
        lang: Language = Language.SPANISH,
        **kwargs
    ) -> Dict[str, Any]:
        """Return error response indicating no LLM available."""
        return {
            "success": False,
            "error": "No LLM provider available for article generation",
            "provider": self.provider_name,
            "suggestion": "Configure an LLM provider or use DummyLLMProvider for testing"
        }


class LLMProviderFactory:
    """Factory for creating LLM provider instances."""
    
    _providers = {
        "dummy": DummyLLMProvider,
        "nollm": NoLLMProvider
    }
    
    @classmethod
    def create_provider(cls, provider_type: str = "dummy", **config) -> LLMProvider:
        """
        Create LLM provider instance.
        
        Args:
            provider_type: Type of provider ("dummy", "nollm", etc.)
            **config: Provider-specific configuration
            
        Returns:
            LLMProvider instance
        """
        if provider_type not in cls._providers:
            logger.warning(f"Unknown provider type: {provider_type}, falling back to dummy")
            provider_type = "dummy"
        
        provider_class = cls._providers[provider_type]
        return provider_class()
    
    @classmethod
    def register_provider(cls, name: str, provider_class):
        """Register a new provider type."""
        cls._providers[name] = provider_class
    
    @classmethod
    def list_providers(cls) -> List[str]:
        """List available provider types."""
        return list(cls._providers.keys())