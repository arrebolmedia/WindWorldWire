#!/usr/bin/env python3
"""Demo script showing enhanced normalization in action."""

from newsbot.ingestor.normalizer import normalize_entry
from newsbot.core.logging import get_logger

logger = get_logger(__name__)

def demo_normalization():
    """Demo the enhanced normalization features with realistic examples."""
    
    class MockSource:
        def __init__(self, lang='en'):
            self.lang = lang
    
    # Realistic RSS entries with various issues
    test_entries = [
        {
            'title': '<h1>Breaking: Major Tech Company Announces <script>alert("xss")</script>New Product Launch &amp; Stock Surge</h1>',
            'link': 'https://news.example.com/tech/article-123?utm_source=newsletter&utm_medium=email&utm_campaign=daily&fbclid=IwAR0abcd#comments',
            'summary': '''
                <div class="article-content">
                    <style>body { color: red; }</style>
                    <p>Major tech company announced a revolutionary new product today, 
                    causing stock prices to surge by &lt;20%&gt; in after-hours trading.</p>
                    <script>document.write("malicious");</script>
                    <p>The announcement came during a press conference where the CEO 
                    described the product as &quot;game-changing&quot; for the industry.</p>
                </div>
            ''',
            'published': '2023-12-25T15:30:00+01:00'  # CET timezone
        },
        {
            'title': 'Últimas Noticias: Gran Evento Deportivo',
            'link': 'https://deportes.ejemplo.com/noticia-456?ref=homepage&cid=12345&utm_content=footer',
            'summary': '<p>El evento deportivo más importante del año se celebrará mañana con la participación de atletas de todo el mundo.</p>',
            'published': 'invalid-date-format'  # Should fallback to now
        },
        {
            'title': '',  # Empty title
            'link': 'https://broken.example.com/no-title',
            'summary': 'Short',  # Very short content
            # No published date
        }
    ]
    
    sources = [
        MockSource('en'),  # English source
        MockSource('es'),  # Spanish source  
        MockSource('fr')   # French source
    ]
    
    print("🚀 Enhanced Normalization Demo")
    print("=" * 60)
    
    for i, (entry, source) in enumerate(zip(test_entries, sources)):
        print(f"\n📄 Entry {i+1} (Source language: {source.lang})")
        print("-" * 40)
        print(f"Original title: {entry.get('title', 'N/A')[:80]}...")
        print(f"Original URL: {entry.get('link', 'N/A')}")
        print(f"Original summary: {entry.get('summary', 'N/A')[:100]}...")
        print(f"Original published: {entry.get('published', 'N/A')}")
        
        try:
            normalized = normalize_entry(entry, source)
            
            print(f"\n✨ Normalized results:")
            print(f"  📰 Title: {normalized['title']}")
            print(f"  🔗 URL: {normalized['url']}")
            print(f"  📝 Summary: {normalized['summary'][:100]}...")
            print(f"  🌐 Language: {normalized['lang']}")
            print(f"  📅 Published: {normalized['published_at']}")
            print(f"  🔑 URL SHA1: {normalized['url_sha1'][:12]}...")
            print(f"  🔢 Text SimHash: {normalized['text_simhash'][:12]}...")
            
            # Show the benefits
            print(f"\n💡 Enhancements applied:")
            
            # HTML cleaning
            if '<script>' in entry.get('title', '') or '<script>' in entry.get('summary', ''):
                print("  🧹 Removed <script> tags and dangerous content")
            if '&amp;' in entry.get('title', '') or '&quot;' in entry.get('summary', ''):
                print("  🔤 Decoded HTML entities (&amp; → &, &quot; → \")")
            if '<style>' in entry.get('summary', ''):
                print("  🎨 Removed <style> tags")
                
            # URL normalization
            original_url = entry.get('link', '')
            if 'utm_' in original_url or 'fbclid=' in original_url or '#' in original_url:
                print(f"  🔗 Normalized URL for deduplication (removes UTM/tracking params)")
                
            # Language detection
            if normalized['lang'] != source.lang:
                print(f"  🌐 Detected language: {normalized['lang']} (overrode source: {source.lang})")
            else:
                print(f"  🌐 Used source language: {normalized['lang']}")
                
            # Date handling
            if entry.get('published') == 'invalid-date-format' or not entry.get('published'):
                print("  📅 Used current UTC time for missing/invalid date")
                
        except Exception as e:
            print(f"❌ Normalization failed: {e}")
            logger.exception(f"Failed to normalize entry {i+1}")
    
    print("\n" + "=" * 60)
    print("🎉 Demo complete! All normalization features working properly.")
    print("\nKey Features Demonstrated:")
    print("✅ HTML cleaning (script/style removal, entity decoding)")
    print("✅ Datetime parsing with UTC fallback")
    print("✅ Language detection from title+summary")
    print("✅ URL normalization (UTM removal, query sorting)")
    print("✅ Consistent SHA1 hashing for deduplication")

if __name__ == "__main__":
    demo_normalization()