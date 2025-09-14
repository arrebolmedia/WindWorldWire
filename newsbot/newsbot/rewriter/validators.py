"""
Validators for anti-hallucination and SEO compliance.

Ensures generated articles meet quality standards and contain no invented information.
All validation functions return detailed feedback for improvement.
"""

import re
import json
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import urlparse
from datetime import datetime

from newsbot.core.logging import get_logger
from newsbot.core.utils import clean_text, sanitize_html, extract_keywords, validate_url
from .models import DraftArticle, ArticleSection, FAQ, SourceLink

logger = get_logger(__name__)


class ValidationResult:
    """Result of a validation check with detailed feedback."""
    
    def __init__(self, is_valid: bool, errors: List[str] = None, warnings: List[str] = None):
        self.is_valid = is_valid
        self.errors = errors or []
        self.warnings = warnings or []
        self.score = self._calculate_score()
    
    def _calculate_score(self) -> float:
        """Calculate quality score (0-100)."""
        if not self.is_valid:
            return max(0, 50 - len(self.errors) * 10)
        return max(60, 100 - len(self.warnings) * 5)
    
    def add_error(self, message: str):
        """Add validation error."""
        self.errors.append(message)
        self.is_valid = False
    
    def add_warning(self, message: str):
        """Add validation warning."""
        self.warnings.append(message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "is_valid": self.is_valid,
            "score": self.score,
            "errors": self.errors,
            "warnings": self.warnings
        }


class AntiHallucinationValidator:
    """
    Validates that article content is supported by source materials.
    
    Prevents fabrication of facts, quotes, data, or events not present in sources.
    """
    
    def __init__(self, strict_mode: bool = True):
        self.strict_mode = strict_mode
    
    def validate_article_against_sources(
        self, 
        article: DraftArticle, 
        source_data: List[Dict[str, Any]]
    ) -> ValidationResult:
        """
        Validate that article content is supported by sources.
        
        Args:
            article: Generated article to validate
            source_data: Original source materials
            
        Returns:
            ValidationResult with detailed feedback
        """
        result = ValidationResult(True)
        
        # Extract all text content from sources
        source_texts = self._extract_source_texts(source_data)
        source_urls = set(item.get('url', '') for item in source_data)
        
        # Validate title claims
        self._validate_title_claims(article.title, source_texts, result)
        
        # Validate lead paragraph
        self._validate_lead_claims(article.lead, source_texts, result)
        
        # Validate key points
        for i, point in enumerate(article.key_points):
            self._validate_key_point_claims(point, source_texts, result, i)
        
        # Validate sections
        for i, section in enumerate(article.sections):
            self._validate_section_claims(section, source_texts, source_urls, result, i)
        
        # Validate FAQs
        for i, faq in enumerate(article.faqs):
            self._validate_faq_claims(faq, source_texts, source_urls, result, i)
        
        # Check for specific numbers/dates/quotes
        self._validate_specific_claims(article, source_texts, result)
        
        return result
    
    def _extract_source_texts(self, source_data: List[Dict[str, Any]]) -> List[str]:
        """Extract all text content from source data."""
        texts = []
        for item in source_data:
            # Combine title, summary, and any content
            combined = ""
            if item.get('title'):
                combined += item['title'] + " "
            if item.get('summary'):
                combined += item['summary'] + " "
            if item.get('content'):
                combined += item['content'] + " "
            
            if combined.strip():
                texts.append(clean_text(combined))
        
        return texts
    
    def _validate_title_claims(self, title: str, source_texts: List[str], result: ValidationResult):
        """Validate claims in the title."""
        # Extract key claims from title
        title_words = set(clean_text(title.lower()).split())
        
        # Check for clickbait patterns
        clickbait_phrases = [
            'increíble', 'shocking', 'no creerás', 'secreto', 'truco',
            'jamás imaginarías', 'te sorprenderá', 'nadie esperaba'
        ]
        
        for phrase in clickbait_phrases:
            if phrase in title.lower():
                result.add_warning(f"Título contiene lenguaje clickbait: '{phrase}'")
        
        # Check if title claims are supported
        if not self._find_supporting_text(title, source_texts, threshold=0.3):
            result.add_error("Título no parece estar respaldado por las fuentes")
    
    def _validate_lead_claims(self, lead: str, source_texts: List[str], result: ValidationResult):
        """Validate claims in the lead paragraph."""
        if not self._find_supporting_text(lead, source_texts, threshold=0.4):
            result.add_error("Lead contiene información no respaldada por fuentes")
    
    def _validate_key_point_claims(self, point: str, source_texts: List[str], result: ValidationResult, index: int):
        """Validate individual key point."""
        if not self._find_supporting_text(point, source_texts, threshold=0.3):
            result.add_error(f"Punto clave {index + 1} no está respaldado por fuentes")
    
    def _validate_section_claims(
        self, 
        section: ArticleSection, 
        source_texts: List[str], 
        source_urls: set,
        result: ValidationResult, 
        index: int
    ):
        """Validate section content and attribution."""
        # Check content support
        content_text = sanitize_html(section.content, strip=True)
        if not self._find_supporting_text(content_text, source_texts, threshold=0.4):
            result.add_error(f"Sección {index + 1} '{section.heading}' contiene información no respaldada")
        
        # Validate source URLs
        for url in section.source_urls:
            if str(url) not in source_urls:
                result.add_warning(f"Sección {index + 1} referencia URL no incluida en fuentes: {url}")
    
    def _validate_faq_claims(
        self, 
        faq: FAQ, 
        source_texts: List[str], 
        source_urls: set,
        result: ValidationResult, 
        index: int
    ):
        """Validate FAQ content."""
        if not self._find_supporting_text(faq.answer, source_texts, threshold=0.4):
            result.add_error(f"FAQ {index + 1} contiene respuesta no respaldada por fuentes")
        
        # Validate source URLs
        for url in faq.source_urls:
            if str(url) not in source_urls:
                result.add_warning(f"FAQ {index + 1} referencia URL no incluida en fuentes: {url}")
    
    def _validate_specific_claims(self, article: DraftArticle, source_texts: List[str], result: ValidationResult):
        """Validate specific numbers, dates, quotes that are common hallucinations."""
        # Combine all article text
        all_text = f"{article.title} {article.lead} "
        for section in article.sections:
            all_text += sanitize_html(section.content, strip=True) + " "
        for faq in article.faqs:
            all_text += f"{faq.question} {faq.answer} "
        
        # Check for specific numbers
        numbers = re.findall(r'\b\d+(?:\.\d+)?%?\b', all_text)
        for number in numbers:
            if not self._find_number_in_sources(number, source_texts):
                result.add_warning(f"Número específico '{number}' no encontrado en fuentes")
        
        # Check for quotes
        quotes = re.findall(r'"([^"]+)"', all_text)
        for quote in quotes:
            if len(quote) > 20 and not self._find_quote_in_sources(quote, source_texts):
                result.add_error(f"Cita '{quote[:50]}...' no encontrada en fuentes")
        
        # Check for specific dates
        dates = re.findall(r'\b\d{1,2}\s+de\s+\w+\s+de\s+\d{4}\b', all_text)
        for date in dates:
            if not self._find_date_in_sources(date, source_texts):
                result.add_warning(f"Fecha específica '{date}' no encontrada en fuentes")
    
    def _find_supporting_text(self, claim: str, source_texts: List[str], threshold: float = 0.3) -> bool:
        """Check if claim is supported by source texts."""
        claim_words = set(clean_text(claim.lower()).split())
        
        for source_text in source_texts:
            source_words = set(clean_text(source_text.lower()).split())
            
            # Calculate word overlap
            overlap = len(claim_words.intersection(source_words))
            coverage = overlap / len(claim_words) if claim_words else 0
            
            if coverage >= threshold:
                return True
        
        return False
    
    def _find_number_in_sources(self, number: str, source_texts: List[str]) -> bool:
        """Check if specific number appears in sources."""
        for source_text in source_texts:
            if number in source_text:
                return True
        return False
    
    def _find_quote_in_sources(self, quote: str, source_texts: List[str]) -> bool:
        """Check if quote appears in sources."""
        quote_lower = quote.lower()
        for source_text in source_texts:
            if quote_lower in source_text.lower():
                return True
        return False
    
    def _find_date_in_sources(self, date: str, source_texts: List[str]) -> bool:
        """Check if specific date appears in sources."""
        for source_text in source_texts:
            if date in source_text:
                return True
        return False


class SEOComplianceValidator:
    """
    Validates SEO compliance and technical requirements.
    
    Ensures articles meet search engine optimization standards.
    """
    
    def validate_seo_compliance(self, article: DraftArticle) -> ValidationResult:
        """
        Validate comprehensive SEO compliance.
        
        Args:
            article: Article to validate
            
        Returns:
            ValidationResult with SEO feedback
        """
        result = ValidationResult(True)
        
        # Validate title
        self._validate_title_seo(article.title, result)
        
        # Validate meta description
        self._validate_meta_description(article.meta_description, result)
        
        # Validate slug
        self._validate_slug(article.slug, result)
        
        # Validate content structure
        self._validate_content_structure(article, result)
        
        # Validate keyword usage
        self._validate_keyword_optimization(article, result)
        
        # Validate technical elements
        self._validate_technical_seo(article, result)
        
        return result
    
    def _validate_title_seo(self, title: str, result: ValidationResult):
        """Validate title SEO compliance."""
        length = len(title)
        
        if length < 30:
            result.add_error(f"Título muy corto ({length} chars). Mínimo 30 caracteres para SEO")
        elif length > 70:
            result.add_error(f"Título muy largo ({length} chars). Máximo 70 caracteres para SEO")
        
        # Check for title case issues
        if title.isupper():
            result.add_warning("Título en mayúsculas. Considera usar title case")
        
        # Check for pipe or colon separators
        if ' | ' in title or ': ' in title:
            result.add_warning("Título contiene separadores. Considera simplificar para SEO")
    
    def _validate_meta_description(self, meta_desc: str, result: ValidationResult):
        """Validate meta description SEO compliance."""
        length = len(meta_desc)
        
        if length < 120:
            result.add_error(f"Meta description muy corta ({length} chars). Mínimo 120 para SEO")
        elif length > 160:
            result.add_error(f"Meta description muy larga ({length} chars). Máximo 160 para SEO")
        
        # Check for call-to-action
        cta_words = ['conoce', 'descubre', 'aprende', 'lee', 'explora', 'consulta']
        if not any(word in meta_desc.lower() for word in cta_words):
            result.add_warning("Meta description podría beneficiarse de un call-to-action")
    
    def _validate_slug(self, slug: str, result: ValidationResult):
        """Validate URL slug compliance."""
        # Check format
        if not re.match(r'^[a-z0-9-]+$', slug):
            result.add_error("Slug debe contener solo letras minúsculas, números y guiones")
        
        # Check length
        if len(slug) < 10:
            result.add_warning(f"Slug corto ({len(slug)} chars). Considera ser más descriptivo")
        elif len(slug) > 100:
            result.add_error(f"Slug muy largo ({len(slug)} chars). Máximo 100 caracteres")
        
        # Check for common issues
        if slug.startswith('-') or slug.endswith('-'):
            result.add_error("Slug no puede empezar o terminar con guión")
        
        if '--' in slug:
            result.add_error("Slug no puede contener guiones consecutivos")
    
    def _validate_content_structure(self, article: DraftArticle, result: ValidationResult):
        """Validate content structure for SEO."""
        # Check section count
        if len(article.sections) < 2:
            result.add_error("Artículo necesita al menos 2 secciones para buena estructura SEO")
        
        # Check content length
        total_content_length = sum(len(sanitize_html(s.content, strip=True)) for s in article.sections)
        
        if total_content_length < 300:
            result.add_warning(f"Contenido corto ({total_content_length} chars). Considera expandir para mejor SEO")
        elif total_content_length > 3000:
            result.add_warning(f"Contenido muy largo ({total_content_length} chars). Considera dividir o resumir")
        
        # Check heading structure
        self._validate_heading_structure(article.sections, result)
    
    def _validate_heading_structure(self, sections: List[ArticleSection], result: ValidationResult):
        """Validate heading hierarchy."""
        for i, section in enumerate(sections):
            heading = section.heading
            
            # Check heading length
            if len(heading) < 5:
                result.add_warning(f"Heading {i+1} muy corto: '{heading}'")
            elif len(heading) > 120:
                result.add_warning(f"Heading {i+1} muy largo ({len(heading)} chars)")
            
            # Check for all caps
            if heading.isupper():
                result.add_warning(f"Heading {i+1} en mayúsculas. Usar title case")
    
    def _validate_keyword_optimization(self, article: DraftArticle, result: ValidationResult):
        """Validate keyword usage and density."""
        # Extract all text content
        all_text = f"{article.title} {article.lead} {article.meta_description} "
        for section in article.sections:
            all_text += f"{section.heading} {sanitize_html(section.content, strip=True)} "
        
        # Extract keywords from content
        keywords = extract_keywords(all_text, max_keywords=10)
        
        if len(keywords) < 3:
            result.add_warning("Pocas palabras clave identificadas. Considera usar términos más específicos")
        
        # Check keyword in title
        title_words = set(clean_text(article.title.lower()).split())
        if not any(keyword in title_words for keyword in keywords[:3]):
            result.add_warning("Palabras clave principales no aparecen en el título")
        
        # Check keyword in meta description
        meta_words = set(clean_text(article.meta_description.lower()).split())
        if not any(keyword in meta_words for keyword in keywords[:3]):
            result.add_warning("Palabras clave principales no aparecen en meta description")
    
    def _validate_technical_seo(self, article: DraftArticle, result: ValidationResult):
        """Validate technical SEO elements."""
        # Validate JSON-LD
        try:
            json_ld_dict = article.json_ld.dict()
            
            # Check required fields
            required_fields = ['headline', 'description', 'datePublished', 'dateModified']
            for field in required_fields:
                if not json_ld_dict.get(field):
                    result.add_error(f"JSON-LD falta campo requerido: {field}")
            
            # Validate headline matches title
            if json_ld_dict.get('headline') != article.title:
                result.add_warning("JSON-LD headline no coincide con título del artículo")
            
        except Exception as e:
            result.add_error(f"Error en JSON-LD: {str(e)}")
        
        # Validate source links
        if len(article.source_links) < 2:
            result.add_error("Artículo necesita al menos 2 fuentes para credibilidad SEO")
        
        # Check domain diversity
        domains = set(link.domain for link in article.source_links)
        if len(domains) < 2:
            result.add_warning("Todas las fuentes del mismo dominio. Considera diversificar")
        
        # Validate image alt text
        if not article.image_alt or len(article.image_alt) < 20:
            result.add_error("Alt text de imagen muy corto o ausente")
        
        if 'cortesía' not in article.image_alt.lower():
            result.add_error("Alt text debe incluir atribución 'Cortesía de...'")


class ContentQualityValidator:
    """
    Validates overall content quality and readability.
    """
    
    def validate_content_quality(self, article: DraftArticle) -> ValidationResult:
        """
        Validate overall content quality.
        
        Args:
            article: Article to validate
            
        Returns:
            ValidationResult with quality feedback
        """
        result = ValidationResult(True)
        
        # Check readability
        self._validate_readability(article, result)
        
        # Check coherence and flow
        self._validate_coherence(article, result)
        
        # Check completeness
        self._validate_completeness(article, result)
        
        # Check language quality
        self._validate_language_quality(article, result)
        
        return result
    
    def _validate_readability(self, article: DraftArticle, result: ValidationResult):
        """Validate content readability."""
        # Combine content for analysis
        all_content = article.lead
        for section in article.sections:
            all_content += " " + sanitize_html(section.content, strip=True)
        
        sentences = re.split(r'[.!?]+', all_content)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if not sentences:
            result.add_error("No se encontraron oraciones válidas en el contenido")
            return
        
        # Average sentence length
        avg_sentence_length = sum(len(s.split()) for s in sentences) / len(sentences)
        
        if avg_sentence_length > 25:
            result.add_warning(f"Oraciones muy largas (promedio {avg_sentence_length:.1f} palabras). Considera simplificar")
        elif avg_sentence_length < 8:
            result.add_warning(f"Oraciones muy cortas (promedio {avg_sentence_length:.1f} palabras). Considera expandir")
    
    def _validate_coherence(self, article: DraftArticle, result: ValidationResult):
        """Validate logical flow and coherence."""
        # Check that sections build logically
        section_headings = [s.heading for s in article.sections]
        
        # Look for good structure patterns
        has_intro = any(word in section_headings[0].lower() for word in ['contexto', 'antecedentes', 'introducción'])
        has_analysis = any(word in ' '.join(section_headings).lower() for word in ['análisis', 'impacto', 'consecuencias'])
        has_conclusion = any(word in section_headings[-1].lower() for word in ['perspectivas', 'conclusiones', 'futuro'])
        
        if not has_intro:
            result.add_warning("Considera incluir sección de contexto/antecedentes")
        
        if not has_analysis:
            result.add_warning("Considera incluir sección de análisis/impacto")
    
    def _validate_completeness(self, article: DraftArticle, result: ValidationResult):
        """Validate content completeness."""
        # Check if key points are addressed in sections
        key_point_words = set()
        for point in article.key_points:
            key_point_words.update(clean_text(point.lower()).split())
        
        section_words = set()
        for section in article.sections:
            content_text = sanitize_html(section.content, strip=True)
            section_words.update(clean_text(content_text.lower()).split())
        
        coverage = len(key_point_words.intersection(section_words)) / len(key_point_words) if key_point_words else 0
        
        if coverage < 0.5:
            result.add_warning("Los puntos clave no están bien desarrollados en las secciones")
    
    def _validate_language_quality(self, article: DraftArticle, result: ValidationResult):
        """Validate language quality and style."""
        # Check for common issues
        all_text = f"{article.title} {article.lead} {article.meta_description}"
        
        # Check for excessive repetition
        words = clean_text(all_text.lower()).split()
        if len(words) > 0:
            from collections import Counter
            word_counts = Counter(words)
            
            # Find most common words (excluding stopwords)
            common_words = [word for word, count in word_counts.most_common(5) 
                          if count > 3 and word not in SPANISH_STOPWORDS]
            
            if common_words:
                result.add_warning(f"Posible repetición excesiva de palabras: {', '.join(common_words[:3])}")


def validate_complete_article(
    article: DraftArticle, 
    source_data: List[Dict[str, Any]],
    strict_hallucination_check: bool = True
) -> Dict[str, ValidationResult]:
    """
    Run complete validation suite on article.
    
    Args:
        article: Article to validate
        source_data: Source materials for hallucination checking
        strict_hallucination_check: Whether to use strict anti-hallucination validation
        
    Returns:
        Dictionary with validation results for each category
    """
    results = {}
    
    # Anti-hallucination validation
    hallucination_validator = AntiHallucinationValidator(strict_mode=strict_hallucination_check)
    results['hallucination'] = hallucination_validator.validate_article_against_sources(article, source_data)
    
    # SEO compliance validation
    seo_validator = SEOComplianceValidator()
    results['seo'] = seo_validator.validate_seo_compliance(article)
    
    # Content quality validation
    quality_validator = ContentQualityValidator()
    results['quality'] = quality_validator.validate_content_quality(article)
    
    return results