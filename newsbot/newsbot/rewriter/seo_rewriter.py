"""
SEO Article Rewriter - Main logic for converting clusters to publication-ready articles.

This module orchestrates the complete rewriting process:
1. Loads and preprocesses cluster data
2. Generates structured article using LLM
3. Validates against sources and SEO standards
4. Iteratively improves until quality thresholds are met
5. Returns publication-ready article with metadata
"""

import asyncio
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from pathlib import Path

from newsbot.core.logging import get_logger
from newsbot.core.utils import (
    clean_text, 
    sanitize_html, 
    generate_slug, 
    extract_keywords,
    validate_url
)
from .models import DraftArticle, ArticleSection, FAQ, SourceLink, JSONLDNewsArticle
from .llm_provider import LLMProviderFactory, LLMProvider
from .validators import (
    validate_complete_article,
    ValidationResult,
    AntiHallucinationValidator,
    SEOComplianceValidator,
    ContentQualityValidator
)

logger = get_logger(__name__)


class RewriteError(Exception):
    """Exception raised during article rewriting process."""
    pass


class SEOArticleRewriter:
    """
    Main rewriter class that converts clusters to SEO-optimized articles.
    
    Handles the complete pipeline from raw cluster data to publication-ready content
    with comprehensive validation and iterative improvement.
    """
    
    def __init__(
        self,
        llm_provider: Optional[LLMProvider] = None,
        max_iterations: int = 3,
        min_quality_score: float = 75.0,
        strict_validation: bool = True
    ):
        """
        Initialize the SEO Article Rewriter.
        
        Args:
            llm_provider: LLM provider instance (uses factory if None)
            max_iterations: Maximum improvement iterations
            min_quality_score: Minimum quality score to accept
            strict_validation: Whether to use strict anti-hallucination validation
        """
        self.llm_provider = llm_provider or LLMProviderFactory.get_provider()
        self.max_iterations = max_iterations
        self.min_quality_score = min_quality_score
        self.strict_validation = strict_validation
        
        # Load prompt template
        self.prompt_template = self._load_prompt_template()
        
        logger.info(f"Initialized SEOArticleRewriter with provider: {type(self.llm_provider).__name__}")
    
    def _load_prompt_template(self) -> str:
        """Load the SEO prompt template."""
        try:
            prompt_path = Path(__file__).parent.parent.parent / "prompts" / "seo.md"
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.warning("SEO prompt template not found, using basic template")
            return self._get_basic_prompt_template()
    
    def _get_basic_prompt_template(self) -> str:
        """Get basic prompt template as fallback."""
        return """
Convierte el siguiente cluster de noticias en un artículo periodístico estructurado.

REGLAS ANTI-ALUCINACIÓN:
1. Solo usa información presente en las fuentes proporcionadas
2. No inventes datos, fechas, nombres o cifras
3. No agregues contexto no presente en las fuentes
4. Atribuye todas las afirmaciones a las fuentes correspondientes

CLUSTER DATA:
{cluster_data}

SOURCES:
{sources}

Responde ÚNICAMENTE con JSON válido siguiendo esta estructura:
{
  "title": "Título SEO-optimizado (30-70 caracteres)",
  "slug": "url-slug-seo-friendly",
  "meta_description": "Meta description SEO (120-160 caracteres)",
  "lead": "Párrafo principal que resume la noticia",
  "key_points": ["Punto clave 1", "Punto clave 2", "Punto clave 3"],
  "sections": [
    {
      "heading": "Encabezado de sección",
      "content": "<p>Contenido HTML de la sección</p>",
      "source_urls": ["url1", "url2"]
    }
  ],
  "faqs": [
    {
      "question": "¿Pregunta frecuente?",
      "answer": "Respuesta basada en fuentes",
      "source_urls": ["url1"]
    }
  ],
  "image_alt": "Descripción de imagen. Cortesía de [fuente]"
}
"""
    
    async def rewrite_cluster_to_article(
        self, 
        cluster_data: Dict[str, Any], 
        language: str = "es"
    ) -> Tuple[DraftArticle, Dict[str, ValidationResult]]:
        """
        Convert a cluster to a publication-ready article.
        
        Args:
            cluster_data: Cluster information with sources
            language: Target language for the article
            
        Returns:
            Tuple of (DraftArticle, validation_results)
            
        Raises:
            RewriteError: If rewriting fails after max iterations
        """
        logger.info(f"Starting rewrite process for cluster: {cluster_data.get('topic', 'Unknown')}")
        
        # Preprocess cluster data
        processed_cluster = self._preprocess_cluster_data(cluster_data)
        source_data = processed_cluster.get('sources', [])
        
        if not source_data:
            raise RewriteError("No source data found in cluster")
        
        # Generate initial article
        article = await self._generate_initial_article(processed_cluster, language)
        
        # Iterative improvement
        best_article = article
        best_score = 0.0
        
        for iteration in range(self.max_iterations):
            logger.info(f"Validation iteration {iteration + 1}/{self.max_iterations}")
            
            # Validate current article
            validation_results = validate_complete_article(
                article=article,
                source_data=source_data,
                strict_hallucination_check=self.strict_validation
            )
            
            # Calculate overall score
            overall_score = self._calculate_overall_score(validation_results)
            
            logger.info(f"Iteration {iteration + 1} score: {overall_score:.1f}")
            
            # Keep best version
            if overall_score > best_score:
                best_article = article
                best_score = overall_score
            
            # Check if we meet quality threshold
            if overall_score >= self.min_quality_score:
                logger.info(f"Quality threshold met: {overall_score:.1f} >= {self.min_quality_score}")
                return best_article, validation_results
            
            # Generate improvement suggestions
            if iteration < self.max_iterations - 1:
                improvement_suggestions = self._generate_improvement_suggestions(validation_results)
                
                # Retry generation with improvements
                article = await self._regenerate_with_improvements(
                    processed_cluster, 
                    language, 
                    improvement_suggestions
                )
        
        # Return best article even if not meeting threshold
        final_validation = validate_complete_article(
            article=best_article,
            source_data=source_data,
            strict_hallucination_check=self.strict_validation
        )
        
        logger.warning(f"Max iterations reached. Best score: {best_score:.1f}")
        return best_article, final_validation
    
    def _preprocess_cluster_data(self, cluster_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Preprocess and validate cluster data.
        
        Args:
            cluster_data: Raw cluster data
            
        Returns:
            Processed cluster data with validated sources
        """
        processed = cluster_data.copy()
        
        # Ensure required fields
        processed.setdefault('topic', 'Noticia')
        processed.setdefault('summary', '')
        processed.setdefault('sources', [])
        
        # Clean and validate sources
        clean_sources = []
        for source in processed['sources']:
            if isinstance(source, dict) and source.get('url'):
                clean_source = {
                    'url': source['url'],
                    'title': clean_text(source.get('title', '')),
                    'summary': clean_text(source.get('summary', '')),
                    'content': clean_text(source.get('content', '')),
                    'published_date': source.get('published_date'),
                    'domain': self._extract_domain(source['url'])
                }
                clean_sources.append(clean_source)
        
        processed['sources'] = clean_sources
        
        # Generate metadata
        processed['cluster_id'] = cluster_data.get('id', f"cluster_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        processed['processed_at'] = datetime.now(timezone.utc).isoformat()
        
        return processed
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        try:
            from urllib.parse import urlparse
            return urlparse(url).netloc
        except:
            return "unknown"
    
    async def _generate_initial_article(
        self, 
        cluster_data: Dict[str, Any], 
        language: str
    ) -> DraftArticle:
        """
        Generate initial article using LLM.
        
        Args:
            cluster_data: Processed cluster data
            language: Target language
            
        Returns:
            Initial DraftArticle
        """
        # Prepare prompt
        prompt = self._prepare_prompt(cluster_data, language)
        
        # Generate with LLM
        try:
            response = await self.llm_provider.generate_article(cluster_data, language, prompt)
            
            # Parse response to DraftArticle
            article = self._parse_llm_response(response, cluster_data)
            
            logger.info(f"Generated initial article: '{article.title}'")
            return article
            
        except Exception as e:
            logger.error(f"Error generating initial article: {str(e)}")
            # Fallback to structured article
            return self._create_fallback_article(cluster_data, language)
    
    def _prepare_prompt(self, cluster_data: Dict[str, Any], language: str) -> str:
        """Prepare the prompt for LLM generation."""
        # Format cluster data
        cluster_info = {
            'topic': cluster_data.get('topic', ''),
            'summary': cluster_data.get('summary', ''),
            'cluster_id': cluster_data.get('cluster_id', ''),
            'source_count': len(cluster_data.get('sources', []))
        }
        
        # Format sources
        sources_info = []
        for i, source in enumerate(cluster_data.get('sources', []), 1):
            source_text = f"FUENTE {i}:\n"
            source_text += f"URL: {source.get('url', '')}\n"
            source_text += f"Título: {source.get('title', '')}\n"
            source_text += f"Resumen: {source.get('summary', '')}\n"
            if source.get('content'):
                source_text += f"Contenido: {source['content'][:500]}...\n"
            source_text += "\n"
            sources_info.append(source_text)
        
        # Replace placeholders in template
        prompt = self.prompt_template.format(
            cluster_data=json.dumps(cluster_info, indent=2, ensure_ascii=False),
            sources='\n'.join(sources_info),
            language=language
        )
        
        return prompt
    
    def _parse_llm_response(self, response: str, cluster_data: Dict[str, Any]) -> DraftArticle:
        """
        Parse LLM response into DraftArticle.
        
        Args:
            response: Raw LLM response
            cluster_data: Original cluster data for fallback
            
        Returns:
            Parsed DraftArticle
        """
        try:
            # Try to extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = response[json_start:json_end]
                article_data = json.loads(json_str)
                
                # Create DraftArticle from parsed data
                return self._create_article_from_data(article_data, cluster_data)
            else:
                raise ValueError("No valid JSON found in response")
                
        except Exception as e:
            logger.error(f"Error parsing LLM response: {str(e)}")
            # Return fallback article
            return self._create_fallback_article(cluster_data, "es")
    
    def _create_article_from_data(
        self, 
        article_data: Dict[str, Any], 
        cluster_data: Dict[str, Any]
    ) -> DraftArticle:
        """Create DraftArticle from parsed data."""
        # Extract source URLs from cluster
        source_urls = [source['url'] for source in cluster_data.get('sources', [])]
        source_domains = list(set(self._extract_domain(url) for url in source_urls))
        
        # Create sections
        sections = []
        for section_data in article_data.get('sections', []):
            section = ArticleSection(
                heading=section_data.get('heading', ''),
                content=sanitize_html(section_data.get('content', '')),
                source_urls=section_data.get('source_urls', source_urls[:2])
            )
            sections.append(section)
        
        # Create FAQs
        faqs = []
        for faq_data in article_data.get('faqs', []):
            faq = FAQ(
                question=faq_data.get('question', ''),
                answer=faq_data.get('answer', ''),
                source_urls=faq_data.get('source_urls', source_urls[:1])
            )
            faqs.append(faq)
        
        # Create source links
        source_links = []
        for url in source_urls:
            domain = self._extract_domain(url)
            source_link = SourceLink(
                url=url,
                title=f"Fuente: {domain}",
                domain=domain
            )
            source_links.append(source_link)
        
        # Create JSON-LD
        json_ld = JSONLDNewsArticle(
            headline=article_data.get('title', ''),
            description=article_data.get('meta_description', ''),
            datePublished=datetime.now(timezone.utc),
            dateModified=datetime.now(timezone.utc),
            author_name="Wind World Wire",
            publisher_name="Wind World Wire",
            url=f"https://windworldwire.com/news/{article_data.get('slug', '')}"
        )
        
        # Create main article
        article = DraftArticle(
            title=article_data.get('title', cluster_data.get('topic', 'Noticia')),
            slug=article_data.get('slug', generate_slug(article_data.get('title', 'noticia'))),
            meta_description=article_data.get('meta_description', ''),
            lead=article_data.get('lead', ''),
            key_points=article_data.get('key_points', []),
            sections=sections,
            faqs=faqs,
            source_links=source_links,
            json_ld=json_ld,
            image_alt=article_data.get('image_alt', 'Imagen de noticia. Cortesía de fuentes.')
        )
        
        return article
    
    def _create_fallback_article(
        self, 
        cluster_data: Dict[str, Any], 
        language: str
    ) -> DraftArticle:
        """Create a basic fallback article when LLM generation fails."""
        topic = cluster_data.get('topic', 'Noticia')
        sources = cluster_data.get('sources', [])
        
        # Basic title and meta
        title = f"Últimas noticias: {topic}"
        slug = generate_slug(title)
        meta_description = f"Conoce las últimas actualizaciones sobre {topic}. Información verificada de fuentes confiables."
        
        # Basic content
        lead = f"Se han reportado nuevos desarrollos relacionados con {topic}."
        
        if cluster_data.get('summary'):
            lead = cluster_data['summary']
        
        # Create basic sections
        sections = [
            ArticleSection(
                heading="Contexto",
                content=f"<p>{lead}</p>",
                source_urls=[sources[0]['url']] if sources else []
            )
        ]
        
        if len(sources) > 1:
            sections.append(
                ArticleSection(
                    heading="Detalles",
                    content="<p>Se están analizando múltiples fuentes para proporcionar información completa.</p>",
                    source_urls=[source['url'] for source in sources[:2]]
                )
            )
        
        # Create source links
        source_links = [
            SourceLink(
                url=source['url'],
                title=source.get('title', f"Fuente {i+1}"),
                domain=self._extract_domain(source['url'])
            )
            for i, source in enumerate(sources)
        ]
        
        # JSON-LD
        json_ld = JSONLDNewsArticle(
            headline=title,
            description=meta_description,
            datePublished=datetime.now(timezone.utc),
            dateModified=datetime.now(timezone.utc),
            author_name="Wind World Wire",
            publisher_name="Wind World Wire",
            url=f"https://windworldwire.com/news/{slug}"
        )
        
        return DraftArticle(
            title=title,
            slug=slug,
            meta_description=meta_description,
            lead=lead,
            key_points=[f"Actualizaciones sobre {topic}", "Información de fuentes verificadas"],
            sections=sections,
            faqs=[],
            source_links=source_links,
            json_ld=json_ld,
            image_alt=f"Imagen relacionada con {topic}. Cortesía de fuentes."
        )
    
    def _calculate_overall_score(self, validation_results: Dict[str, ValidationResult]) -> float:
        """Calculate overall quality score from validation results."""
        scores = []
        weights = {
            'hallucination': 0.4,  # Most important - no false information
            'seo': 0.35,          # SEO compliance
            'quality': 0.25       # Content quality
        }
        
        for category, result in validation_results.items():
            weight = weights.get(category, 0.33)
            scores.append(result.score * weight)
        
        return sum(scores)
    
    def _generate_improvement_suggestions(
        self, 
        validation_results: Dict[str, ValidationResult]
    ) -> List[str]:
        """Generate improvement suggestions from validation results."""
        suggestions = []
        
        for category, result in validation_results.items():
            if result.errors:
                suggestions.extend([f"[{category.upper()}] {error}" for error in result.errors])
            
            if result.warnings:
                suggestions.extend([f"[{category.upper()} WARNING] {warning}" for warning in result.warnings[:2]])
        
        return suggestions[:5]  # Limit to top 5 suggestions
    
    async def _regenerate_with_improvements(
        self,
        cluster_data: Dict[str, Any],
        language: str,
        suggestions: List[str]
    ) -> DraftArticle:
        """Regenerate article with improvement suggestions."""
        # Add improvement context to prompt
        improvement_context = "\n".join([
            "MEJORAS REQUERIDAS:",
            *[f"- {suggestion}" for suggestion in suggestions],
            "\nRevisa y corrige estos aspectos en la nueva versión.\n"
        ])
        
        enhanced_prompt = improvement_context + self._prepare_prompt(cluster_data, language)
        
        try:
            response = await self.llm_provider.generate_article(cluster_data, language, enhanced_prompt)
            return self._parse_llm_response(response, cluster_data)
        except Exception as e:
            logger.error(f"Error in regeneration: {str(e)}")
            return self._create_fallback_article(cluster_data, language)


async def rewrite_cluster_quick(cluster_data: Dict[str, Any], language: str = "es") -> DraftArticle:
    """
    Quick rewrite function for simple use cases.
    
    Args:
        cluster_data: Cluster information
        language: Target language
        
    Returns:
        Rewritten article
    """
    rewriter = SEOArticleRewriter(max_iterations=1, min_quality_score=60.0)
    article, _ = await rewriter.rewrite_cluster_to_article(cluster_data, language)
    return article


async def rewrite_cluster_comprehensive(
    cluster_data: Dict[str, Any], 
    language: str = "es",
    max_iterations: int = 3,
    min_quality_score: float = 80.0
) -> Tuple[DraftArticle, Dict[str, ValidationResult]]:
    """
    Comprehensive rewrite with full validation.
    
    Args:
        cluster_data: Cluster information
        language: Target language
        max_iterations: Maximum improvement iterations
        min_quality_score: Minimum quality threshold
        
    Returns:
        Tuple of (article, validation_results)
    """
    rewriter = SEOArticleRewriter(
        max_iterations=max_iterations,
        min_quality_score=min_quality_score,
        strict_validation=True
    )
    
    return await rewriter.rewrite_cluster_to_article(cluster_data, language)


# Spanish stopwords for keyword extraction
SPANISH_STOPWORDS = {
    'el', 'la', 'de', 'que', 'y', 'a', 'en', 'un', 'es', 'se', 'no', 'te', 'lo', 'le', 'da', 'su', 'por', 'son', 
    'con', 'para', 'al', 'una', 'ser', 'ya', 'todo', 'está', 'muy', 'han', 'me', 'si', 'sin', 'sobre', 'este', 
    'fue', 'hasta', 'hay', 'donde', 'quien', 'desde', 'todos', 'durante', 'pero', 'entre', 'cuando', 'él', 
    'más', 'esta', 'sus', 'les', 'como', 'del', 'tiempo', 'ver', 'sólo', 'años', 'estado', 'pueden', 'tienen',
    'ser', 'estar', 'haber', 'tener', 'hacer', 'poder', 'decir', 'ir', 'ver', 'dar', 'saber', 'querer',
    'cosa', 'otro', 'mismo', 'vez', 'forma', 'parte', 'caso', 'día', 'momento', 'manera', 'lugar', 'año'
}