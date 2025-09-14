"""
Template renderer for converting DraftArticle to publication-ready HTML.

Generates safe, SEO-optimized HTML with proper escaping, structured data,
and accessibility features for publication systems.
"""

import html
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from newsbot.core.logging import get_logger
from newsbot.core.utils import sanitize_html
from .models import DraftArticle, ArticleSection, FAQ, SourceLink

logger = get_logger(__name__)


class TemplateRenderer:
    """
    Renders DraftArticle to publication-ready HTML templates.
    
    Provides multiple output formats optimized for different publication systems.
    """
    
    def __init__(self, template_dir: Optional[Path] = None):
        """
        Initialize template renderer.
        
        Args:
            template_dir: Directory containing custom templates (optional)
        """
        self.template_dir = template_dir
        
    def render_complete_article(
        self, 
        article: DraftArticle, 
        template_type: str = "default"
    ) -> str:
        """
        Render complete article HTML.
        
        Args:
            article: Article to render
            template_type: Template style ("default", "amp", "wordpress")
            
        Returns:
            Complete HTML article
        """
        if template_type == "amp":
            return self._render_amp_article(article)
        elif template_type == "wordpress":
            return self._render_wordpress_article(article)
        else:
            return self._render_default_article(article)
    
    def render_article_preview(self, article: DraftArticle) -> str:
        """
        Render article preview for CMS preview.
        
        Args:
            article: Article to preview
            
        Returns:
            Preview HTML
        """
        return self._render_preview_template(article)
    
    def render_social_card(self, article: DraftArticle) -> Dict[str, str]:
        """
        Generate social media card data.
        
        Args:
            article: Article for social card
            
        Returns:
            Dictionary with social card metadata
        """
        return {
            "title": article.title,
            "description": article.meta_description,
            "image_alt": article.image_alt,
            "url": f"https://windworldwire.com/news/{article.slug}",
            "type": "article",
            "site": "Wind World Wire"
        }
    
    def _render_default_article(self, article: DraftArticle) -> str:
        """Render default article template."""
        # HTML head with SEO metadata
        head_html = self._render_head_metadata(article)
        
        # Article header
        header_html = self._render_article_header(article)
        
        # Article body
        body_html = self._render_article_body(article)
        
        # Article footer with sources
        footer_html = self._render_article_footer(article)
        
        # JSON-LD structured data
        jsonld_html = self._render_json_ld(article)
        
        # Combine all parts
        full_html = f"""<!DOCTYPE html>
<html lang="es">
{head_html}
<body>
    <article class="news-article" itemscope itemtype="https://schema.org/NewsArticle">
        {header_html}
        {body_html}
        {footer_html}
    </article>
    {jsonld_html}
</body>
</html>"""
        
        return full_html
    
    def _render_amp_article(self, article: DraftArticle) -> str:
        """Render AMP-optimized article."""
        # AMP-specific metadata
        amp_head = self._render_amp_head(article)
        
        # AMP article structure
        amp_body = f"""
        <article class="amp-article">
            <header class="amp-header">
                <h1 itemprop="headline">{html.escape(article.title)}</h1>
                <div class="amp-meta">
                    <time datetime="{article.json_ld.datePublished.isoformat()}" itemprop="datePublished">
                        {article.json_ld.datePublished.strftime('%d/%m/%Y')}
                    </time>
                    <span class="amp-author" itemprop="author">Wind World Wire</span>
                </div>
            </header>
            
            <div class="amp-lead">
                <p class="lead-paragraph">{html.escape(article.lead)}</p>
            </div>
            
            <div class="amp-content" itemprop="articleBody">
                {self._render_sections_amp(article.sections)}
            </div>
            
            {self._render_faqs_amp(article.faqs)}
            {self._render_sources_amp(article.source_links)}
        </article>
        """
        
        return f"""<!doctype html>
<html ⚡ lang="es">
{amp_head}
<body>
    {amp_body}
    {self._render_json_ld(article)}
</body>
</html>"""
    
    def _render_wordpress_article(self, article: DraftArticle) -> str:
        """Render WordPress-compatible article."""
        # WordPress post content (no HTML/body wrapper)
        content = f"""
<!-- wp:paragraph {{"className":"lead-paragraph"}} -->
<p class="lead-paragraph">{html.escape(article.lead)}</p>
<!-- /wp:paragraph -->

{self._render_sections_wordpress(article.sections)}

{self._render_faqs_wordpress(article.faqs)}

{self._render_sources_wordpress(article.source_links)}
"""
        
        return content.strip()
    
    def _render_head_metadata(self, article: DraftArticle) -> str:
        """Render HTML head with SEO metadata."""
        return f"""<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    
    <!-- SEO Meta Tags -->
    <title>{html.escape(article.title)}</title>
    <meta name="description" content="{html.escape(article.meta_description)}">
    <meta name="robots" content="index, follow">
    <link rel="canonical" href="https://windworldwire.com/news/{article.slug}">
    
    <!-- Open Graph -->
    <meta property="og:type" content="article">
    <meta property="og:title" content="{html.escape(article.title)}">
    <meta property="og:description" content="{html.escape(article.meta_description)}">
    <meta property="og:url" content="https://windworldwire.com/news/{article.slug}">
    <meta property="og:site_name" content="Wind World Wire">
    <meta property="article:published_time" content="{article.json_ld.datePublished.isoformat()}">
    <meta property="article:modified_time" content="{article.json_ld.dateModified.isoformat()}">
    <meta property="article:author" content="Wind World Wire">
    
    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{html.escape(article.title)}">
    <meta name="twitter:description" content="{html.escape(article.meta_description)}">
    <meta name="twitter:site" content="@WindWorldWire">
    
    <!-- Article CSS -->
    <style>
        .news-article {{ max-width: 800px; margin: 0 auto; padding: 20px; font-family: Georgia, serif; line-height: 1.6; }}
        .article-header {{ margin-bottom: 30px; }}
        .article-title {{ font-size: 2.2em; font-weight: bold; margin-bottom: 15px; color: #1a1a1a; }}
        .article-meta {{ color: #666; font-size: 0.9em; margin-bottom: 20px; }}
        .lead-paragraph {{ font-size: 1.2em; font-weight: 500; color: #333; margin-bottom: 25px; }}
        .key-points {{ background: #f8f9fa; padding: 20px; border-left: 4px solid #007bff; margin: 25px 0; }}
        .key-points h3 {{ margin-top: 0; color: #007bff; }}
        .article-section {{ margin: 30px 0; }}
        .section-heading {{ font-size: 1.5em; font-weight: bold; margin-bottom: 15px; color: #1a1a1a; }}
        .faqs {{ margin: 40px 0; }}
        .faq-item {{ margin: 20px 0; border: 1px solid #e9ecef; border-radius: 5px; }}
        .faq-question {{ font-weight: bold; padding: 15px; background: #f8f9fa; margin: 0; cursor: pointer; }}
        .faq-answer {{ padding: 15px; }}
        .sources {{ margin: 40px 0; padding: 20px; background: #f8f9fa; border-radius: 5px; }}
        .source-link {{ display: block; margin: 5px 0; color: #007bff; text-decoration: none; }}
        .source-link:hover {{ text-decoration: underline; }}
    </style>
</head>"""
    
    def _render_amp_head(self, article: DraftArticle) -> str:
        """Render AMP-specific head."""
        return f"""<head>
    <meta charset="utf-8">
    <script async src="https://cdn.ampproject.org/v0.js"></script>
    <title>{html.escape(article.title)}</title>
    <link rel="canonical" href="https://windworldwire.com/news/{article.slug}">
    <meta name="viewport" content="width=device-width,minimum-scale=1,initial-scale=1">
    <meta name="description" content="{html.escape(article.meta_description)}">
    
    <!-- AMP CSS -->
    <style amp-custom>
        .amp-article {{ max-width: 700px; margin: 0 auto; padding: 15px; font-family: Georgia, serif; }}
        .amp-header {{ margin-bottom: 25px; }}
        .amp-header h1 {{ font-size: 1.8em; line-height: 1.3; margin-bottom: 10px; }}
        .amp-meta {{ color: #666; font-size: 0.9em; }}
        .amp-lead {{ font-size: 1.1em; margin-bottom: 20px; }}
        .amp-section {{ margin: 20px 0; }}
        .amp-section h2 {{ font-size: 1.3em; margin-bottom: 10px; }}
    </style>
    
    <style amp-boilerplate>body{{-webkit-animation:-amp-start 8s steps(1,end) 0s 1 normal both;-moz-animation:-amp-start 8s steps(1,end) 0s 1 normal both;-ms-animation:-amp-start 8s steps(1,end) 0s 1 normal both;animation:-amp-start 8s steps(1,end) 0s 1 normal both}}@-webkit-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-moz-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-ms-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@-o-keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}@keyframes -amp-start{{from{{visibility:hidden}}to{{visibility:visible}}}}</style><noscript><style amp-boilerplate>body{{-webkit-animation:none;-moz-animation:none;-ms-animation:none;animation:none}}</style></noscript>
</head>"""
    
    def _render_article_header(self, article: DraftArticle) -> str:
        """Render article header section."""
        return f"""
        <header class="article-header">
            <h1 class="article-title" itemprop="headline">{html.escape(article.title)}</h1>
            <div class="article-meta">
                <time datetime="{article.json_ld.datePublished.isoformat()}" itemprop="datePublished">
                    {article.json_ld.datePublished.strftime('%d de %B, %Y')}
                </time>
                <span class="article-author" itemprop="author">Wind World Wire</span>
            </div>
        </header>"""
    
    def _render_article_body(self, article: DraftArticle) -> str:
        """Render main article content."""
        body_html = f"""
        <div class="article-content" itemprop="articleBody">
            <div class="lead-paragraph">
                <p>{html.escape(article.lead)}</p>
            </div>
            
            {self._render_key_points(article.key_points)}
            {self._render_sections(article.sections)}
            {self._render_faqs(article.faqs)}
        </div>"""
        
        return body_html
    
    def _render_key_points(self, key_points: List[str]) -> str:
        """Render key points section."""
        if not key_points:
            return ""
        
        points_html = "\n".join([f"<li>{html.escape(point)}</li>" for point in key_points])
        
        return f"""
        <div class="key-points">
            <h3>Puntos Clave</h3>
            <ul>
                {points_html}
            </ul>
        </div>"""
    
    def _render_sections(self, sections: List[ArticleSection]) -> str:
        """Render article sections."""
        sections_html = []
        
        for section in sections:
            # Sanitize content but preserve basic HTML
            safe_content = sanitize_html(section.content, allowed_tags=['p', 'strong', 'em', 'a', 'ul', 'ol', 'li'])
            
            section_html = f"""
            <section class="article-section">
                <h2 class="section-heading">{html.escape(section.heading)}</h2>
                <div class="section-content">
                    {safe_content}
                </div>
            </section>"""
            
            sections_html.append(section_html)
        
        return "\n".join(sections_html)
    
    def _render_sections_amp(self, sections: List[ArticleSection]) -> str:
        """Render sections for AMP."""
        sections_html = []
        
        for section in sections:
            safe_content = sanitize_html(section.content, allowed_tags=['p', 'strong', 'em'])
            
            section_html = f"""
            <section class="amp-section">
                <h2>{html.escape(section.heading)}</h2>
                {safe_content}
            </section>"""
            
            sections_html.append(section_html)
        
        return "\n".join(sections_html)
    
    def _render_sections_wordpress(self, sections: List[ArticleSection]) -> str:
        """Render sections for WordPress."""
        sections_html = []
        
        for section in sections:
            safe_content = sanitize_html(section.content, allowed_tags=['p', 'strong', 'em', 'a', 'ul', 'ol', 'li'])
            
            section_html = f"""
<!-- wp:heading {{"level":2}} -->
<h2>{html.escape(section.heading)}</h2>
<!-- /wp:heading -->

{safe_content}
"""
            sections_html.append(section_html)
        
        return "\n".join(sections_html)
    
    def _render_faqs(self, faqs: List[FAQ]) -> str:
        """Render FAQ section."""
        if not faqs:
            return ""
        
        faq_items = []
        for i, faq in enumerate(faqs):
            faq_html = f"""
            <div class="faq-item" itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
                <h3 class="faq-question" itemprop="name">{html.escape(faq.question)}</h3>
                <div class="faq-answer" itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
                    <div itemprop="text">{html.escape(faq.answer)}</div>
                </div>
            </div>"""
            faq_items.append(faq_html)
        
        return f"""
        <section class="faqs" itemscope itemtype="https://schema.org/FAQPage">
            <h2>Preguntas Frecuentes</h2>
            {"".join(faq_items)}
        </section>"""
    
    def _render_faqs_amp(self, faqs: List[FAQ]) -> str:
        """Render FAQs for AMP."""
        if not faqs:
            return ""
        
        faq_items = []
        for faq in faqs:
            faq_html = f"""
            <div class="amp-faq">
                <h3>{html.escape(faq.question)}</h3>
                <p>{html.escape(faq.answer)}</p>
            </div>"""
            faq_items.append(faq_html)
        
        return f"""
        <section class="amp-faqs">
            <h2>Preguntas Frecuentes</h2>
            {"".join(faq_items)}
        </section>"""
    
    def _render_faqs_wordpress(self, faqs: List[FAQ]) -> str:
        """Render FAQs for WordPress."""
        if not faqs:
            return ""
        
        faq_items = []
        for faq in faqs:
            faq_html = f"""
<!-- wp:heading {{"level":3}} -->
<h3>{html.escape(faq.question)}</h3>
<!-- /wp:heading -->

<!-- wp:paragraph -->
<p>{html.escape(faq.answer)}</p>
<!-- /wp:paragraph -->
"""
            faq_items.append(faq_html)
        
        return f"""
<!-- wp:heading {{"level":2}} -->
<h2>Preguntas Frecuentes</h2>
<!-- /wp:heading -->

{"".join(faq_items)}
"""
    
    def _render_article_footer(self, article: DraftArticle) -> str:
        """Render article footer with sources."""
        return f"""
        <footer class="article-footer">
            {self._render_sources(article.source_links)}
        </footer>"""
    
    def _render_sources(self, source_links: List[SourceLink]) -> str:
        """Render source links."""
        if not source_links:
            return ""
        
        source_items = []
        for source in source_links:
            source_html = f'<a href="{html.escape(str(source.url))}" class="source-link" target="_blank" rel="noopener">{html.escape(source.title)}</a>'
            source_items.append(source_html)
        
        return f"""
        <div class="sources">
            <h3>Fuentes</h3>
            <div class="source-list">
                {"<br>".join(source_items)}
            </div>
        </div>"""
    
    def _render_sources_amp(self, source_links: List[SourceLink]) -> str:
        """Render sources for AMP."""
        if not source_links:
            return ""
        
        source_items = []
        for source in source_links:
            source_html = f'<a href="{html.escape(str(source.url))}">{html.escape(source.title)}</a>'
            source_items.append(source_html)
        
        return f"""
        <div class="amp-sources">
            <h2>Fuentes</h2>
            <div>
                {"<br>".join(source_items)}
            </div>
        </div>"""
    
    def _render_sources_wordpress(self, source_links: List[SourceLink]) -> str:
        """Render sources for WordPress."""
        if not source_links:
            return ""
        
        source_items = []
        for source in source_links:
            source_html = f'<a href="{html.escape(str(source.url))}" target="_blank" rel="noopener">{html.escape(source.title)}</a>'
            source_items.append(f"<li>{source_html}</li>")
        
        return f"""
<!-- wp:heading {{"level":2}} -->
<h2>Fuentes</h2>
<!-- /wp:heading -->

<!-- wp:list -->
<ul>
{"".join(source_items)}
</ul>
<!-- /wp:list -->
"""
    
    def _render_json_ld(self, article: DraftArticle) -> str:
        """Render JSON-LD structured data."""
        json_ld_data = article.json_ld.dict()
        
        # Convert datetime objects to ISO format
        for key, value in json_ld_data.items():
            if isinstance(value, datetime):
                json_ld_data[key] = value.isoformat()
        
        json_ld_str = json.dumps(json_ld_data, ensure_ascii=False, indent=2)
        
        return f"""
    <script type="application/ld+json">
    {json_ld_str}
    </script>"""
    
    def _render_preview_template(self, article: DraftArticle) -> str:
        """Render simplified preview template."""
        return f"""
        <div class="article-preview">
            <h1>{html.escape(article.title)}</h1>
            <p class="meta-description">{html.escape(article.meta_description)}</p>
            <div class="lead">
                <p>{html.escape(article.lead)}</p>
            </div>
            <div class="sections-preview">
                {self._render_sections_preview(article.sections)}
            </div>
            <div class="metadata">
                <p><strong>Slug:</strong> {article.slug}</p>
                <p><strong>Fuentes:</strong> {len(article.source_links)}</p>
                <p><strong>Secciones:</strong> {len(article.sections)}</p>
                <p><strong>FAQs:</strong> {len(article.faqs)}</p>
            </div>
        </div>"""
    
    def _render_sections_preview(self, sections: List[ArticleSection]) -> str:
        """Render sections preview."""
        if not sections:
            return "<p>No hay secciones</p>"
        
        preview_items = []
        for section in sections[:3]:  # Show only first 3 sections
            content_preview = sanitize_html(section.content, strip=True)[:100] + "..."
            preview_items.append(f"""
            <div class="section-preview">
                <h3>{html.escape(section.heading)}</h3>
                <p>{html.escape(content_preview)}</p>
            </div>""")
        
        if len(sections) > 3:
            preview_items.append(f"<p><em>... y {len(sections) - 3} secciones más</em></p>")
        
        return "".join(preview_items)


def render_article_html(article: DraftArticle, template_type: str = "default") -> str:
    """
    Convenience function to render article to HTML.
    
    Args:
        article: Article to render
        template_type: Template type ("default", "amp", "wordpress")
        
    Returns:
        Rendered HTML
    """
    renderer = TemplateRenderer()
    return renderer.render_complete_article(article, template_type)


def render_article_preview(article: DraftArticle) -> str:
    """
    Convenience function to render article preview.
    
    Args:
        article: Article to preview
        
    Returns:
        Preview HTML
    """
    renderer = TemplateRenderer()
    return renderer.render_article_preview(article)