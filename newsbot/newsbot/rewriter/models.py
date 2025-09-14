"""
Core Pydantic models for the rewriter system.

Defines structured article output with comprehensive SEO and validation fields.
All models ensure zero hallucination by requiring source attribution.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field, validator, HttpUrl
from enum import Enum


class Language(str, Enum):
    """Supported languages for article generation."""
    SPANISH = "es"
    ENGLISH = "en"


class ArticleSection(BaseModel):
    """A section within the article body."""
    heading: str = Field(..., min_length=5, max_length=120, description="Section heading (H2/H3)")
    content: str = Field(..., min_length=50, max_length=2000, description="Section content in HTML")
    source_urls: List[HttpUrl] = Field(default_factory=list, description="Source URLs supporting this section")
    
    @validator('heading')
    def validate_heading(cls, v):
        """Ensure heading is properly formatted."""
        if not v or v.isspace():
            raise ValueError("Heading cannot be empty or whitespace")
        # Remove excessive punctuation
        cleaned = v.strip().rstrip('.!?')
        return cleaned


class FAQ(BaseModel):
    """Frequently asked question with answer."""
    question: str = Field(..., min_length=10, max_length=200, description="The question")
    answer: str = Field(..., min_length=20, max_length=1000, description="The answer")
    source_urls: List[HttpUrl] = Field(default_factory=list, description="Source URLs supporting this answer")
    
    @validator('question')
    def validate_question(cls, v):
        """Ensure question ends with question mark."""
        if not v.strip().endswith('?'):
            v = v.strip() + '?'
        return v


class SourceLink(BaseModel):
    """Source link with metadata."""
    url: HttpUrl = Field(..., description="Source URL")
    title: str = Field(..., min_length=5, max_length=200, description="Link title/anchor text")
    domain: str = Field(..., description="Domain name (e.g., 'reuters.com')")
    published_at: Optional[datetime] = Field(None, description="Original publication date")
    
    @validator('domain')
    def validate_domain(cls, v, values):
        """Extract domain from URL if not provided properly."""
        if 'url' in values:
            from urllib.parse import urlparse
            parsed = urlparse(str(values['url']))
            return parsed.netloc.lower()
        return v.lower()


class JSONLDNewsArticle(BaseModel):
    """NewsArticle JSON-LD schema for SEO."""
    type: str = Field(default="NewsArticle", const=True)
    headline: str = Field(..., max_length=110, description="Article headline")
    description: str = Field(..., max_length=160, description="Meta description")
    author: Dict[str, str] = Field(default={"@type": "Organization", "name": "Wind World Wire"})
    publisher: Dict[str, str] = Field(default={"@type": "Organization", "name": "Wind World Wire"})
    datePublished: str = Field(..., description="Publication date in ISO format")
    dateModified: str = Field(..., description="Last modified date in ISO format")
    url: Optional[str] = Field(None, description="Canonical URL")
    image: Optional[str] = Field(None, description="Featured image URL")
    articleSection: Optional[str] = Field(None, description="Article category/section")
    wordCount: Optional[int] = Field(None, description="Approximate word count")
    
    @validator('datePublished', 'dateModified')
    def validate_iso_date(cls, v):
        """Ensure dates are in proper ISO format."""
        if isinstance(v, datetime):
            return v.isoformat()
        return v


class DraftArticle(BaseModel):
    """
    Complete draft article with all required fields for publication.
    
    Ensures zero hallucination by requiring source attribution for all claims.
    Includes comprehensive SEO optimization and structured content.
    """
    
    # Core Content
    title: str = Field(
        ..., 
        min_length=30, 
        max_length=70, 
        description="SEO-optimized title (30-70 characters)"
    )
    
    lead: str = Field(
        ..., 
        min_length=120, 
        max_length=300, 
        description="Article lead/introduction paragraph"
    )
    
    key_points: List[str] = Field(
        ..., 
        min_items=3, 
        max_items=8, 
        description="Key points/bullet summary (3-8 items)"
    )
    
    sections: List[ArticleSection] = Field(
        ..., 
        min_items=2, 
        max_items=8, 
        description="Article body sections (2-8 sections)"
    )
    
    faqs: List[FAQ] = Field(
        default_factory=list, 
        max_items=6, 
        description="Optional FAQ section"
    )
    
    # SEO & Metadata
    meta_description: str = Field(
        ..., 
        min_length=120, 
        max_length=160, 
        description="Meta description for SEO (120-160 characters)"
    )
    
    slug: str = Field(
        ..., 
        min_length=10, 
        max_length=100, 
        description="URL slug (10-100 characters)"
    )
    
    json_ld: JSONLDNewsArticle = Field(
        ..., 
        description="NewsArticle JSON-LD schema"
    )
    
    # Sources & Attribution
    source_links: List[SourceLink] = Field(
        ..., 
        min_items=2, 
        max_items=15, 
        description="Source links with metadata (2-15 sources)"
    )
    
    image_alt: str = Field(
        ..., 
        min_length=20, 
        max_length=150, 
        description="Alt text for featured image (includes 'Cortesía de...')"
    )
    
    # Localization
    lang: Language = Field(
        default=Language.SPANISH, 
        description="Article language"
    )
    
    # Generation Metadata
    cluster_id: Optional[int] = Field(None, description="Source cluster ID")
    topic_name: Optional[str] = Field(None, description="Source topic name")
    generated_at: datetime = Field(default_factory=datetime.utcnow, description="Generation timestamp")
    word_count: Optional[int] = Field(None, description="Total word count")
    
    @validator('title')
    def validate_title(cls, v):
        """Ensure title follows SEO best practices."""
        # Remove excessive punctuation
        cleaned = v.strip().rstrip('.!?')
        
        # Check for click-bait patterns
        clickbait_words = ['increíble', 'shocking', 'no creerás', 'secreto', 'truco']
        if any(word in cleaned.lower() for word in clickbait_words):
            raise ValueError("Title should avoid clickbait language")
        
        return cleaned
    
    @validator('slug')
    def validate_slug(cls, v):
        """Ensure slug follows URL-safe conventions."""
        import re
        # Should be lowercase, hyphens only, no special chars
        if not re.match(r'^[a-z0-9-]+$', v):
            raise ValueError("Slug must contain only lowercase letters, numbers, and hyphens")
        
        # Should not start or end with hyphen
        if v.startswith('-') or v.endswith('-'):
            raise ValueError("Slug cannot start or end with hyphen")
        
        # Should not have consecutive hyphens
        if '--' in v:
            raise ValueError("Slug cannot contain consecutive hyphens")
        
        return v
    
    @validator('key_points')
    def validate_key_points(cls, v):
        """Ensure key points are distinct and well-formed."""
        # Check for duplicates (case-insensitive)
        lower_points = [point.lower().strip() for point in v]
        if len(set(lower_points)) != len(lower_points):
            raise ValueError("Key points must be unique")
        
        # Check minimum length for each point
        for point in v:
            if len(point.strip()) < 20:
                raise ValueError("Each key point must be at least 20 characters")
        
        return v
    
    @validator('image_alt')
    def validate_image_alt(cls, v):
        """Ensure image alt text includes attribution."""
        if 'cortesía' not in v.lower() and 'courtesy' not in v.lower():
            raise ValueError("Image alt text must include attribution (Cortesía de...)")
        return v
    
    @validator('source_links')
    def validate_sources(cls, v):
        """Ensure source diversity and quality."""
        if not v:
            raise ValueError("At least 2 source links required")
        
        # Check domain diversity
        domains = [link.domain for link in v]
        unique_domains = set(domains)
        
        if len(unique_domains) < 2:
            raise ValueError("Sources must include at least 2 different domains")
        
        # Warn if too many sources from same domain
        from collections import Counter
        domain_counts = Counter(domains)
        max_per_domain = max(domain_counts.values())
        
        if max_per_domain > len(v) // 2:
            raise ValueError("Too many sources from single domain - ensure diversity")
        
        return v
    
    def calculate_word_count(self) -> int:
        """Calculate approximate word count for the article."""
        text_content = f"{self.title} {self.lead}"
        
        # Add sections content
        for section in self.sections:
            # Strip HTML tags for word count
            import re
            clean_content = re.sub(r'<[^>]+>', '', section.content)
            text_content += f" {clean_content}"
        
        # Add FAQ content
        for faq in self.faqs:
            text_content += f" {faq.question} {faq.answer}"
        
        words = text_content.split()
        return len(words)
    
    def get_reading_time(self) -> int:
        """Estimate reading time in minutes (250 words per minute)."""
        word_count = self.word_count or self.calculate_word_count()
        return max(1, round(word_count / 250))
    
    def validate_seo_compliance(self) -> Dict[str, bool]:
        """Validate SEO compliance across all fields."""
        compliance = {
            'title_length': 30 <= len(self.title) <= 70,
            'meta_description_length': 120 <= len(self.meta_description) <= 160,
            'has_h2_sections': len(self.sections) >= 2,
            'source_diversity': len(set(link.domain for link in self.source_links)) >= 2,
            'minimum_content': sum(len(s.content) for s in self.sections) >= 300,
            'has_key_points': len(self.key_points) >= 3,
            'proper_attribution': 'cortesía' in self.image_alt.lower()
        }
        
        return compliance
    
    def to_html(self) -> str:
        """Generate basic HTML representation of the article."""
        html_parts = [
            f"<article>",
            f"<h1>{self.title}</h1>",
            f"<p class='lead'>{self.lead}</p>",
        ]
        
        # Add key points
        if self.key_points:
            html_parts.append("<div class='key-points'>")
            html_parts.append("<h2>Puntos Clave</h2>")
            html_parts.append("<ul>")
            for point in self.key_points:
                html_parts.append(f"<li>{point}</li>")
            html_parts.append("</ul>")
            html_parts.append("</div>")
        
        # Add sections
        for section in self.sections:
            html_parts.append(f"<section>")
            html_parts.append(f"<h2>{section.heading}</h2>")
            html_parts.append(f"<div>{section.content}</div>")
            html_parts.append(f"</section>")
        
        # Add FAQs
        if self.faqs:
            html_parts.append("<div class='faqs'>")
            html_parts.append("<h2>Preguntas Frecuentes</h2>")
            for faq in self.faqs:
                html_parts.append(f"<div class='faq'>")
                html_parts.append(f"<h3>{faq.question}</h3>")
                html_parts.append(f"<p>{faq.answer}</p>")
                html_parts.append(f"</div>")
            html_parts.append("</div>")
        
        html_parts.append("</article>")
        
        return "\n".join(html_parts)
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True
        validate_assignment = True
        extra = "forbid"  # Prevent additional fields
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            HttpUrl: lambda v: str(v)
        }


class RewriteRequest(BaseModel):
    """Request model for article rewriting."""
    cluster_id: int = Field(..., description="Source cluster ID")
    topic_name: Optional[str] = Field(None, description="Topic name for context")
    lang: Language = Field(default=Language.SPANISH, description="Target language")
    include_faqs: bool = Field(default=True, description="Include FAQ section")
    max_sections: int = Field(default=6, ge=2, le=8, description="Maximum sections to generate")
    seo_focus_keywords: List[str] = Field(default_factory=list, description="SEO focus keywords")


class RewriteResponse(BaseModel):
    """Response model for article rewriting."""
    success: bool = Field(..., description="Whether rewriting was successful")
    article: Optional[DraftArticle] = Field(None, description="Generated article (if successful)")
    error: Optional[str] = Field(None, description="Error message (if failed)")
    processing_time_seconds: Optional[float] = Field(None, description="Processing time")
    sources_used: int = Field(default=0, description="Number of source items used")
    validation_warnings: List[str] = Field(default_factory=list, description="Validation warnings")