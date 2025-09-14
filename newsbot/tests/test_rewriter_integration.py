"""
Integration tests for the article rewriter system.

Tests the complete pipeline from cluster data to publication-ready articles
with comprehensive validation and multiple output formats.
"""

import pytest
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List

from fastapi.testclient import TestClient
from newsbot.rewriter.app import app
from newsbot.rewriter.models import DraftArticle, ArticleSection, FAQ, SourceLink
from newsbot.rewriter.seo_rewriter import SEOArticleRewriter, rewrite_cluster_quick, rewrite_cluster_comprehensive
from newsbot.rewriter.validators import (
    validate_complete_article,
    AntiHallucinationValidator,
    SEOComplianceValidator,
    ContentQualityValidator
)
from newsbot.rewriter.template_renderer import TemplateRenderer, render_article_html, render_article_preview
from newsbot.rewriter.llm_provider import DummyLLMProvider, LLMProviderFactory

# Test client
client = TestClient(app)


class TestRewriterModels:
    """Test Pydantic models and validation."""
    
    def test_draft_article_creation(self):
        """Test DraftArticle model creation and validation."""
        article_data = {
            "title": "Test Article Title for SEO Optimization",
            "slug": "test-article-title-for-seo-optimization",
            "meta_description": "This is a comprehensive meta description for testing purposes that meets the minimum length requirements for SEO.",
            "lead": "This is the lead paragraph that introduces the main topic.",
            "key_points": ["Point 1", "Point 2", "Point 3"],
            "sections": [
                {
                    "heading": "Test Section",
                    "content": "<p>Test section content</p>",
                    "source_urls": ["https://example.com"]
                }
            ],
            "faqs": [
                {
                    "question": "What is this test about?",
                    "answer": "This is a test question and answer.",
                    "source_urls": ["https://example.com"]
                }
            ],
            "source_links": [
                {
                    "url": "https://example.com",
                    "title": "Example Source",
                    "domain": "example.com"
                }
            ],
            "image_alt": "Test image description. Cortesía de Example Source."
        }
        
        article = DraftArticle(**article_data)
        
        assert article.title == "Test Article Title for SEO Optimization"
        assert len(article.sections) == 1
        assert len(article.faqs) == 1
        assert len(article.source_links) == 1
        assert article.json_ld is not None
    
    def test_article_validation_errors(self):
        """Test validation errors for invalid article data."""
        # Test title too short
        with pytest.raises(ValueError, match="Title too short"):
            DraftArticle(
                title="Short",  # Too short
                slug="short",
                meta_description="Valid meta description that meets the minimum length requirements for SEO optimization and testing.",
                lead="Valid lead paragraph",
                key_points=[],
                sections=[],
                faqs=[],
                source_links=[],
                image_alt="Valid alt text"
            )
        
        # Test meta description too short
        with pytest.raises(ValueError, match="Meta description too short"):
            DraftArticle(
                title="Valid Title for Testing SEO Validation",
                slug="valid-title-for-testing-seo-validation",
                meta_description="Short",  # Too short
                lead="Valid lead paragraph",
                key_points=[],
                sections=[],
                faqs=[],
                source_links=[],
                image_alt="Valid alt text"
            )
    
    def test_slug_validation(self):
        """Test slug format validation."""
        # Valid slug
        article = DraftArticle(
            title="Valid Title for Testing SEO Validation Rules",
            slug="valid-title-for-testing-seo-validation-rules",
            meta_description="Valid meta description that meets the minimum length requirements for SEO optimization and testing purposes.",
            lead="Valid lead paragraph",
            key_points=[],
            sections=[],
            faqs=[],
            source_links=[],
            image_alt="Valid alt text"
        )
        assert article.slug == "valid-title-for-testing-seo-validation-rules"
        
        # Invalid slug with uppercase
        with pytest.raises(ValueError, match="lowercase"):
            DraftArticle(
                title="Valid Title for Testing SEO Validation Rules",
                slug="Invalid-Slug-With-Uppercase",
                meta_description="Valid meta description that meets the minimum length requirements for SEO optimization and testing purposes.",
                lead="Valid lead paragraph",
                key_points=[],
                sections=[],
                faqs=[],
                source_links=[],
                image_alt="Valid alt text"
            )


class TestLLMProvider:
    """Test LLM provider functionality."""
    
    @pytest.mark.asyncio
    async def test_dummy_llm_provider(self):
        """Test DummyLLMProvider generates valid content."""
        provider = DummyLLMProvider()
        
        cluster_data = {
            "topic": "Test Topic",
            "summary": "Test summary",
            "sources": [
                {
                    "url": "https://example.com/test",
                    "title": "Test Source",
                    "summary": "Test source summary",
                    "content": "Test source content"
                }
            ]
        }
        
        result = await provider.generate_article(cluster_data, "es")
        
        assert isinstance(result, str)
        assert len(result) > 100
        assert "topic" in result.lower() or "test" in result.lower()
    
    def test_llm_provider_factory(self):
        """Test LLM provider factory returns appropriate provider."""
        provider = LLMProviderFactory.get_provider()
        
        # Should return DummyLLMProvider when no real LLM is configured
        assert isinstance(provider, DummyLLMProvider)


class TestValidators:
    """Test validation system."""
    
    def test_anti_hallucination_validator(self):
        """Test anti-hallucination validation."""
        validator = AntiHallucinationValidator()
        
        # Create test article
        article = DraftArticle(
            title="España Instala Energía Solar Record en 2024",
            slug="espana-instala-energia-solar-record-2024",
            meta_description="España alcanza nuevo récord en instalación de energía solar con 1,200 MW instalados en primer trimestre según datos oficiales.",
            lead="España ha instalado 1,200 MW de energía solar en el primer trimestre de 2024.",
            key_points=["Instalación de 1,200 MW", "Crecimiento del 30%", "Liderazgo de Andalucía"],
            sections=[
                ArticleSection(
                    heading="Datos del Crecimiento",
                    content="<p>Según el Ministerio, se instalaron 1,200 MW de nueva capacidad.</p>",
                    source_urls=["https://example.com/solar"]
                )
            ],
            faqs=[],
            source_links=[
                SourceLink(
                    url="https://example.com/solar",
                    title="Datos Oficiales",
                    domain="example.com"
                )
            ],
            image_alt="Instalación solar. Cortesía de Ministerio."
        )
        
        # Create matching source data
        source_data = [
            {
                "url": "https://example.com/solar",
                "title": "España instala 1,200 MW de energía solar",
                "summary": "Nuevo récord de instalación solar",
                "content": "El Ministerio de Transición Ecológica confirmó la instalación de 1,200 MW de nueva capacidad solar fotovoltaica durante el primer trimestre. Andalucía lideró las instalaciones con un crecimiento del 30%."
            }
        ]
        
        result = validator.validate_article_against_sources(article, source_data)
        
        assert isinstance(result.is_valid, bool)
        assert isinstance(result.score, float)
        assert 0 <= result.score <= 100
    
    def test_seo_compliance_validator(self):
        """Test SEO compliance validation."""
        validator = SEOComplianceValidator()
        
        # Create test article with good SEO
        article = DraftArticle(
            title="España Instala Record de Energía Solar en Primer Trimestre",  # Good length
            slug="espana-instala-record-energia-solar-primer-trimestre",
            meta_description="España alcanza nuevo récord histórico en instalación de energía solar con 1,200 MW instalados durante primer trimestre de 2024.",  # Good length
            lead="España ha establecido un nuevo récord en energía solar.",
            key_points=["Record histórico", "1,200 MW instalados", "Primer trimestre 2024"],
            sections=[
                ArticleSection(
                    heading="Contexto del Crecimiento Solar",
                    content="<p>El sector solar español experimentó crecimiento excepcional.</p>",
                    source_urls=["https://example.com/solar"]
                ),
                ArticleSection(
                    heading="Perspectivas Futuras",
                    content="<p>Las proyecciones indican continuidad del crecimiento.</p>",
                    source_urls=["https://example.com/futuro"]
                )
            ],
            faqs=[
                FAQ(
                    question="¿Cuánto creció el sector solar?",
                    answer="El sector creció un 30% comparado con el año anterior.",
                    source_urls=["https://example.com/solar"]
                )
            ],
            source_links=[
                SourceLink(url="https://example.com/solar", title="Fuente Solar", domain="example.com"),
                SourceLink(url="https://example.com/futuro", title="Fuente Futuro", domain="example.com")
            ],
            image_alt="Instalación de paneles solares en España. Cortesía de Ministerio de Energía."
        )
        
        result = validator.validate_seo_compliance(article)
        
        assert isinstance(result.is_valid, bool)
        assert isinstance(result.score, float)
        assert 0 <= result.score <= 100
        
        # Should have minimal errors for well-optimized article
        assert len(result.errors) <= 2
    
    def test_content_quality_validator(self):
        """Test content quality validation."""
        validator = ContentQualityValidator()
        
        article = DraftArticle(
            title="Análisis Completo del Crecimiento de Energía Solar en España",
            slug="analisis-completo-crecimiento-energia-solar-espana",
            meta_description="Análisis detallado del crecimiento récord del sector de energía solar en España durante 2024 con datos oficiales y proyecciones.",
            lead="El sector de energía solar en España ha experimentado un crecimiento sin precedentes durante 2024.",
            key_points=["Crecimiento récord", "Datos oficiales", "Proyecciones positivas"],
            sections=[
                ArticleSection(
                    heading="Contexto del Sector",
                    content="<p>El contexto energético español favoreció el desarrollo solar. Las políticas gubernamentales han sido determinantes.</p>",
                    source_urls=["https://example.com"]
                ),
                ArticleSection(
                    heading="Análisis de Datos",
                    content="<p>Los datos muestran tendencias positivas. El análisis detallado revela factores clave del crecimiento.</p>",
                    source_urls=["https://example.com"]
                )
            ],
            faqs=[],
            source_links=[SourceLink(url="https://example.com", title="Fuente", domain="example.com")],
            image_alt="Gráfico de crecimiento solar. Cortesía de Instituto de Energía."
        )
        
        result = validator.validate_content_quality(article)
        
        assert isinstance(result.is_valid, bool)
        assert isinstance(result.score, float)


class TestSEORewriter:
    """Test main rewriter functionality."""
    
    @pytest.mark.asyncio
    async def test_rewrite_cluster_quick(self):
        """Test quick rewrite functionality."""
        cluster_data = {
            "topic": "Energía Renovable España",
            "summary": "Crecimiento del sector renovable",
            "sources": [
                {
                    "url": "https://example.com/renovables",
                    "title": "Energía Renovable Crece en España",
                    "summary": "Sector renovable muestra crecimiento",
                    "content": "El sector de energía renovable en España ha mostrado un crecimiento significativo durante 2024."
                }
            ]
        }
        
        article = await rewrite_cluster_quick(cluster_data, "es")
        
        assert isinstance(article, DraftArticle)
        assert len(article.title) >= 30
        assert len(article.meta_description) >= 120
        assert len(article.sections) >= 1
        assert len(article.source_links) >= 1
    
    @pytest.mark.asyncio
    async def test_rewrite_cluster_comprehensive(self):
        """Test comprehensive rewrite with validation."""
        cluster_data = {
            "topic": "Inversión Eólica Marina España",
            "summary": "Record de inversión en eólica marina",
            "sources": [
                {
                    "url": "https://example.com/eolica1",
                    "title": "España Invierte 2,500 Millones en Eólica Marina",
                    "summary": "Inversión récord en proyectos eólicos marinos",
                    "content": "España ha atraído inversiones por 2,500 millones de euros en proyectos de energía eólica marina. Los proyectos se ubican en Galicia, Asturias y País Vasco."
                },
                {
                    "url": "https://example.com/eolica2",
                    "title": "Proyectos Eólicos Marinos Generarán 3,000 Empleos",
                    "summary": "Impacto en empleo de proyectos eólicos",
                    "content": "Los nuevos proyectos de energía eólica marina generarán más de 3,000 empleos directos y contribuirán a los objetivos de descarbonización para 2030."
                }
            ]
        }
        
        article, validation_results = await rewrite_cluster_comprehensive(cluster_data, "es")
        
        assert isinstance(article, DraftArticle)
        assert isinstance(validation_results, dict)
        assert "hallucination" in validation_results
        assert "seo" in validation_results
        assert "quality" in validation_results
        
        # Check validation results structure
        for category, result in validation_results.items():
            assert hasattr(result, 'is_valid')
            assert hasattr(result, 'score')
            assert hasattr(result, 'errors')
            assert hasattr(result, 'warnings')


class TestTemplateRenderer:
    """Test template rendering functionality."""
    
    def test_render_default_article(self):
        """Test default HTML rendering."""
        renderer = TemplateRenderer()
        
        article = DraftArticle(
            title="Test Article Title for HTML Rendering Validation",
            slug="test-article-title-for-html-rendering-validation",
            meta_description="Test meta description for HTML rendering that meets minimum length requirements for comprehensive testing.",
            lead="Test lead paragraph for HTML rendering validation.",
            key_points=["Point 1", "Point 2"],
            sections=[
                ArticleSection(
                    heading="Test Section",
                    content="<p>Test section content with <strong>formatting</strong>.</p>",
                    source_urls=["https://example.com"]
                )
            ],
            faqs=[
                FAQ(
                    question="Test question?",
                    answer="Test answer for the question.",
                    source_urls=["https://example.com"]
                )
            ],
            source_links=[
                SourceLink(url="https://example.com", title="Test Source", domain="example.com")
            ],
            image_alt="Test image. Cortesía de Test Source."
        )
        
        html = renderer.render_complete_article(article, "default")
        
        assert "<!DOCTYPE html>" in html
        assert article.title in html
        assert article.meta_description in html
        assert "Test Section" in html
        assert "Test question?" in html
        assert "Test Source" in html
        assert "schema.org" in html  # JSON-LD
    
    def test_render_wordpress_article(self):
        """Test WordPress-compatible rendering."""
        renderer = TemplateRenderer()
        
        article = DraftArticle(
            title="WordPress Compatible Article Title for Testing",
            slug="wordpress-compatible-article-title-for-testing",
            meta_description="WordPress compatible meta description that meets all length requirements for comprehensive testing validation.",
            lead="WordPress test lead paragraph.",
            key_points=["WP Point 1", "WP Point 2"],
            sections=[
                ArticleSection(
                    heading="WordPress Section",
                    content="<p>WordPress section content.</p>",
                    source_urls=["https://example.com"]
                )
            ],
            faqs=[],
            source_links=[
                SourceLink(url="https://example.com", title="WP Source", domain="example.com")
            ],
            image_alt="WordPress image. Cortesía de WP Source."
        )
        
        html = renderer.render_complete_article(article, "wordpress")
        
        assert "<!-- wp:paragraph" in html
        assert "<!-- wp:heading" in html
        assert "WordPress Section" in html
        assert "<!DOCTYPE html>" not in html  # No full HTML wrapper
    
    def test_render_amp_article(self):
        """Test AMP-compatible rendering."""
        renderer = TemplateRenderer()
        
        article = DraftArticle(
            title="AMP Compatible Article Title for Mobile Testing",
            slug="amp-compatible-article-title-for-mobile-testing",
            meta_description="AMP compatible meta description optimized for mobile devices and fast loading performance testing validation.",
            lead="AMP test lead paragraph for mobile.",
            key_points=["AMP Point 1", "AMP Point 2"],
            sections=[
                ArticleSection(
                    heading="AMP Section",
                    content="<p>AMP section content for mobile.</p>",
                    source_urls=["https://example.com"]
                )
            ],
            faqs=[],
            source_links=[
                SourceLink(url="https://example.com", title="AMP Source", domain="example.com")
            ],
            image_alt="AMP image. Cortesía de AMP Source."
        )
        
        html = renderer.render_complete_article(article, "amp")
        
        assert "⚡" in html  # AMP lightning bolt
        assert "cdn.ampproject.org" in html
        assert "amp-custom" in html
        assert "AMP Section" in html
    
    def test_render_article_preview(self):
        """Test article preview rendering."""
        renderer = TemplateRenderer()
        
        article = DraftArticle(
            title="Preview Article Title for Testing Preview Functionality",
            slug="preview-article-title-for-testing-preview-functionality",
            meta_description="Preview meta description for testing the preview rendering functionality with comprehensive validation.",
            lead="Preview lead paragraph.",
            key_points=["Preview Point 1"],
            sections=[
                ArticleSection(
                    heading="Preview Section",
                    content="<p>Preview section content.</p>",
                    source_urls=["https://example.com"]
                )
            ],
            faqs=[],
            source_links=[
                SourceLink(url="https://example.com", title="Preview Source", domain="example.com")
            ],
            image_alt="Preview image. Cortesía de Preview Source."
        )
        
        html = renderer.render_article_preview(article)
        
        assert "article-preview" in html
        assert article.title in html
        assert "Preview Section" in html
        assert "Slug:" in html
        assert "Fuentes:" in html


class TestAPIEndpoints:
    """Test FastAPI endpoints."""
    
    def test_health_endpoint(self):
        """Test health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "components" in data
    
    def test_root_endpoint(self):
        """Test root endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert data["message"] == "Article Rewriter API"
        assert "endpoints" in data
    
    def test_mock_data_endpoint(self):
        """Test mock data endpoint."""
        response = client.get("/rewrite/mock-data")
        assert response.status_code == 200
        
        data = response.json()
        assert "mock_cluster" in data
        assert "topic" in data["mock_cluster"]
        assert "sources" in data["mock_cluster"]
        assert len(data["mock_cluster"]["sources"]) >= 3
    
    def test_stats_endpoint(self):
        """Test statistics endpoint."""
        response = client.get("/stats")
        assert response.status_code == 200
        
        data = response.json()
        assert "service" in data
        assert "version" in data
        assert "supported_languages" in data
        assert "features" in data
    
    def test_rewrite_endpoint_with_mock_data(self):
        """Test rewrite endpoint with mock data."""
        # Get mock data first
        mock_response = client.get("/rewrite/mock-data")
        mock_data = mock_response.json()["mock_cluster"]
        
        # Create rewrite request
        request_data = {
            "cluster": mock_data,
            "language": "es",
            "quality_mode": "quick",
            "output_format": "json"
        }
        
        response = client.post("/rewrite", json=request_data)
        assert response.status_code == 200
        
        data = response.json()
        assert data["success"] is True
        assert "article" in data
        assert "processing_time" in data
        assert "quality_score" in data
        
        # Check article structure
        article = data["article"]
        assert "title" in article
        assert "meta_description" in article
        assert "sections" in article
        assert "source_links" in article
    
    def test_rewrite_preview_endpoint(self):
        """Test rewrite preview endpoint."""
        # Get mock data
        mock_response = client.get("/rewrite/mock-data")
        mock_data = mock_response.json()["mock_cluster"]
        
        request_data = {
            "cluster": mock_data,
            "language": "es",
            "quality_mode": "quick",
            "output_format": "preview"
        }
        
        response = client.post("/rewrite/preview", json=request_data)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        
        html_content = response.text
        assert "<!DOCTYPE html>" in html_content
        assert "Vista Previa" in html_content
    
    def test_invalid_rewrite_request(self):
        """Test rewrite endpoint with invalid data."""
        request_data = {
            "cluster": {
                "topic": "Test",
                "sources": []  # Empty sources - should fail validation
            }
        }
        
        response = client.post("/rewrite", json=request_data)
        assert response.status_code == 422  # Validation error


class TestIntegrationScenarios:
    """Test complete integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_complete_pipeline_spanish(self):
        """Test complete pipeline for Spanish article."""
        # Realistic Spanish cluster data
        cluster_data = {
            "topic": "Transición Energética en España",
            "summary": "España acelera su transición hacia energías renovables con nuevas políticas y inversiones.",
            "sources": [
                {
                    "url": "https://example.com/transicion1",
                    "title": "España Aprueba Nuevo Plan de Energías Renovables",
                    "summary": "El gobierno español aprueba un ambicioso plan para acelerar la transición energética.",
                    "content": "El Gobierno de España ha aprobado un nuevo Plan Nacional de Energías Renovables que establece objetivos ambiciosos para 2030. El plan incluye inversiones por 50,000 millones de euros y la creación de 250,000 empleos verdes."
                },
                {
                    "url": "https://example.com/transicion2",
                    "title": "Inversión Privada en Renovables Alcanza Record",
                    "summary": "La inversión privada en energías renovables supera todas las expectativas.",
                    "content": "La inversión privada en proyectos de energías renovables en España ha alcanzado un récord histórico de 15,000 millones de euros en 2024. Los proyectos incluyen parques solares, eólicos y de almacenamiento."
                }
            ],
            "cluster_id": "transicion_energetica_2024"
        }
        
        # Test rewriter
        rewriter = SEOArticleRewriter()
        article, validation_results = await rewriter.rewrite_cluster_to_article(cluster_data, "es")
        
        # Validate article structure
        assert isinstance(article, DraftArticle)
        assert "transición" in article.title.lower() or "energía" in article.title.lower()
        assert len(article.sections) >= 2
        assert len(article.source_links) == 2
        
        # Test validation results
        assert len(validation_results) == 3  # hallucination, seo, quality
        
        overall_scores = [result.score for result in validation_results.values()]
        average_score = sum(overall_scores) / len(overall_scores)
        assert average_score > 60  # Should achieve reasonable quality
        
        # Test template rendering
        renderer = TemplateRenderer()
        html_output = renderer.render_complete_article(article, "default")
        assert len(html_output) > 1000
        assert article.title in html_output
        assert "España" in html_output
        
        # Test WordPress format
        wp_output = renderer.render_complete_article(article, "wordpress")
        assert "<!-- wp:" in wp_output
        assert "España" in wp_output
    
    def test_api_complete_workflow(self):
        """Test complete API workflow."""
        # 1. Check health
        health_response = client.get("/health")
        assert health_response.status_code == 200
        
        # 2. Get mock data
        mock_response = client.get("/rewrite/mock-data")
        assert mock_response.status_code == 200
        mock_data = mock_response.json()["mock_cluster"]
        
        # 3. Test different quality modes
        for quality_mode in ["quick", "balanced"]:
            request_data = {
                "cluster": mock_data,
                "language": "es",
                "quality_mode": quality_mode,
                "output_format": "json"
            }
            
            response = client.post("/rewrite", json=request_data)
            assert response.status_code == 200
            
            data = response.json()
            assert data["success"] is True
            assert data["quality_score"] > 0
        
        # 4. Test different output formats
        for output_format in ["html", "wordpress", "preview"]:
            request_data = {
                "cluster": mock_data,
                "language": "es",
                "quality_mode": "quick",
                "output_format": output_format
            }
            
            if output_format == "preview":
                response = client.post("/rewrite/preview", json=request_data)
                assert response.status_code == 200
                assert "text/html" in response.headers["content-type"]
            else:
                response = client.post("/rewrite", json=request_data)
                assert response.status_code == 200
                
                data = response.json()
                assert data["success"] is True
                assert "html" in data["article"]
    
    def test_error_handling(self):
        """Test error handling scenarios."""
        # Invalid cluster data
        invalid_request = {
            "cluster": {
                "topic": "",  # Empty topic
                "sources": []  # No sources
            }
        }
        
        response = client.post("/rewrite", json=invalid_request)
        assert response.status_code == 422
        
        # Invalid language
        invalid_language = {
            "cluster": {
                "topic": "Test Topic",
                "sources": [{"url": "https://example.com", "title": "Test"}]
            },
            "language": "invalid"  # Invalid language
        }
        
        response = client.post("/rewrite", json=invalid_language)
        assert response.status_code == 422


# Performance tests
class TestPerformance:
    """Test performance characteristics."""
    
    @pytest.mark.asyncio
    async def test_rewrite_performance(self):
        """Test rewrite performance with realistic data."""
        import time
        
        cluster_data = {
            "topic": "Desarrollo Sostenible España",
            "summary": "Iniciativas de desarrollo sostenible en España",
            "sources": [
                {
                    "url": f"https://example.com/source{i}",
                    "title": f"Fuente de Desarrollo Sostenible {i}",
                    "summary": f"Resumen de la fuente {i} sobre desarrollo sostenible",
                    "content": f"Contenido detallado de la fuente {i} que habla sobre las iniciativas de desarrollo sostenible en España y su impacto en la sociedad y el medio ambiente."
                }
                for i in range(1, 6)  # 5 sources
            ]
        }
        
        start_time = time.time()
        article = await rewrite_cluster_quick(cluster_data, "es")
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        # Should complete within reasonable time
        assert processing_time < 10.0  # seconds
        assert isinstance(article, DraftArticle)
        assert len(article.sections) >= 1


# Fixtures
@pytest.fixture
def sample_cluster_data():
    """Sample cluster data for testing."""
    return {
        "topic": "Innovación Tecnológica España",
        "summary": "Avances en innovación tecnológica en España",
        "sources": [
            {
                "url": "https://example.com/tech1",
                "title": "España Lidera Innovación en IA",
                "summary": "España se posiciona como líder en inteligencia artificial",
                "content": "España ha emergido como un líder europeo en el desarrollo de inteligencia artificial, con inversiones significativas en investigación y desarrollo."
            },
            {
                "url": "https://example.com/tech2",
                "title": "Startups Tecnológicas Crecen 40%",
                "summary": "Las startups tecnológicas españolas experimentan crecimiento",
                "content": "El ecosistema de startups tecnológicas en España ha crecido un 40% en el último año, atrayendo inversión internacional."
            }
        ],
        "cluster_id": "innovacion_tech_2024"
    }


@pytest.fixture
def sample_article():
    """Sample article for testing."""
    return DraftArticle(
        title="Innovación Tecnológica Impulsa el Crecimiento en España",
        slug="innovacion-tecnologica-impulsa-crecimiento-espana",
        meta_description="España se consolida como líder en innovación tecnológica con crecimiento del 40% en startups y nuevas inversiones en IA.",
        lead="España experimenta un boom tecnológico sin precedentes con crecimiento exponencial en startups e IA.",
        key_points=["Liderazgo en IA", "Crecimiento 40% startups", "Inversión internacional"],
        sections=[
            ArticleSection(
                heading="Contexto de la Innovación",
                content="<p>El contexto actual favorece la innovación tecnológica en España.</p>",
                source_urls=["https://example.com/tech1"]
            ),
            ArticleSection(
                heading="Perspectivas de Crecimiento",
                content="<p>Las perspectivas de crecimiento son muy positivas para el sector.</p>",
                source_urls=["https://example.com/tech2"]
            )
        ],
        faqs=[
            FAQ(
                question="¿Por qué crece tanto el sector tech en España?",
                answer="El crecimiento se debe a políticas favorables y talento disponible.",
                source_urls=["https://example.com/tech1"]
            )
        ],
        source_links=[
            SourceLink(url="https://example.com/tech1", title="Fuente IA", domain="example.com"),
            SourceLink(url="https://example.com/tech2", title="Fuente Startups", domain="example.com")
        ],
        image_alt="Innovación tecnológica en España. Cortesía de Ministerio de Ciencia."
    )


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])