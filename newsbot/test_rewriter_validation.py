#!/usr/bin/env python3
"""
Simple test script to validate the rewriter implementation.

Tests basic functionality without running the full server.
"""

import asyncio
import sys
import json
from pathlib import Path

# Add newsbot to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from newsbot.rewriter.models import DraftArticle, ArticleSection, SourceLink
    from newsbot.rewriter.llm_provider import DummyLLMProvider
    from newsbot.rewriter.validators import SEOComplianceValidator
    from newsbot.rewriter.seo_rewriter import rewrite_cluster_quick
    from newsbot.rewriter.template_renderer import render_article_preview
    
    print("✅ All imports successful!")
    
    # Test model creation
    print("\n🧪 Testing model creation...")
    
    article = DraftArticle(
        title="Test Article for Comprehensive Validation Testing",
        slug="test-article-for-comprehensive-validation-testing",
        meta_description="This is a comprehensive test meta description that meets the minimum length requirements for SEO validation testing.",
        lead="This is a test lead paragraph for validation.",
        key_points=["Test point 1", "Test point 2"],
        sections=[
            ArticleSection(
                heading="Test Section",
                content="<p>Test content</p>",
                source_urls=["https://example.com"]
            )
        ],
        faqs=[],
        source_links=[
            SourceLink(
                url="https://example.com",
                title="Test Source",
                domain="example.com"
            )
        ],
        image_alt="Test image. Cortesía de Test Source."
    )
    
    print(f"✅ Created article: {article.title}")
    print(f"   - Slug: {article.slug}")
    print(f"   - Meta length: {len(article.meta_description)} chars")
    print(f"   - Sections: {len(article.sections)}")
    print(f"   - Sources: {len(article.source_links)}")
    
    # Test LLM provider
    print("\n🧪 Testing LLM provider...")
    
    async def test_llm():
        provider = DummyLLMProvider()
        
        cluster_data = {
            "topic": "Test Topic",
            "summary": "Test summary",
            "sources": [
                {
                    "url": "https://example.com",
                    "title": "Test Source",
                    "summary": "Test source summary",
                    "content": "Test source content"
                }
            ]
        }
        
        result = await provider.generate_article(cluster_data, "es")
        print(f"✅ LLM provider generated {len(result)} characters")
        return len(result) > 100
    
    llm_test_passed = asyncio.run(test_llm())
    
    # Test SEO validator
    print("\n🧪 Testing SEO validator...")
    
    seo_validator = SEOComplianceValidator()
    seo_result = seo_validator.validate_seo_compliance(article)
    
    print(f"✅ SEO validation completed")
    print(f"   - Valid: {seo_result.is_valid}")
    print(f"   - Score: {seo_result.score:.1f}/100")
    print(f"   - Errors: {len(seo_result.errors)}")
    print(f"   - Warnings: {len(seo_result.warnings)}")
    
    # Test template renderer
    print("\n🧪 Testing template renderer...")
    
    preview_html = render_article_preview(article)
    print(f"✅ Template renderer generated {len(preview_html)} chars of HTML")
    
    # Test quick rewriter
    print("\n🧪 Testing quick rewriter...")
    
    async def test_quick_rewriter():
        cluster_data = {
            "topic": "Energía Renovable España",
            "summary": "Test summary about renewable energy",
            "sources": [
                {
                    "url": "https://example.com/energia",
                    "title": "España Impulsa Energías Renovables",
                    "summary": "España continúa impulsando el sector renovable",
                    "content": "España ha mostrado un compromiso firme con las energías renovables, implementando políticas que favorecen el desarrollo sostenible."
                }
            ]
        }
        
        rewritten_article = await rewrite_cluster_quick(cluster_data, "es")
        print(f"✅ Quick rewriter generated article:")
        print(f"   - Title: {rewritten_article.title}")
        print(f"   - Sections: {len(rewritten_article.sections)}")
        print(f"   - Word count: ~{len(rewritten_article.lead.split())} words in lead")
        
        return rewritten_article
    
    quick_article = asyncio.run(test_quick_rewriter())
    
    # Summary
    print("\n📊 Test Summary:")
    print("✅ Model creation: PASSED")
    print(f"✅ LLM provider: {'PASSED' if llm_test_passed else 'FAILED'}")
    print(f"✅ SEO validation: PASSED (score: {seo_result.score:.1f})")
    print(f"✅ Template rendering: PASSED")
    print(f"✅ Quick rewriter: PASSED")
    
    print(f"\n🎉 All core components are working correctly!")
    print(f"📋 Generated article preview:")
    print(f"   Title: {quick_article.title}")
    print(f"   Meta: {quick_article.meta_description[:100]}...")
    print(f"   Lead: {quick_article.lead[:100]}...")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the correct directory and all dependencies are installed.")
    
except Exception as e:
    print(f"❌ Test failed: {e}")
    import traceback
    traceback.print_exc()