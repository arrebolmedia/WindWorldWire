#!/usr/bin/env python3
"""
RSS Ingestor Demo Script

This script demonstrates the RSS ingestion functionality by:
1. Parsing RSS feeds
2. Normalizing content
3. Computing content hashes for deduplication
4. Showing how the pipeline would work

Run this script to see the RSS ingestor in action without needing a database.
"""

import asyncio
from datetime import datetime

from newsbot.ingestor.rss import RSSParser
from newsbot.ingestor.normalizer import DataNormalizer
from newsbot.core.simhash import compute_simhash, are_similar


async def demo_rss_parsing():
    """Demonstrate RSS parsing capabilities."""
    print("🔍 RSS Ingestor Demo")
    print("=" * 50)
    
    # Sample RSS content for demonstration
    sample_rss = """<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
        <channel>
            <title>Demo News Feed</title>
            <description>Sample RSS feed for testing</description>
            <item>
                <title>Breaking: Taiwan Strengthens Cyber Security Measures</title>
                <link>https://example.com/taiwan-cyber-security</link>
                <description><![CDATA[Taiwan announces new cybersecurity initiatives to protect critical infrastructure from potential threats. The measures include enhanced monitoring systems and international cooperation agreements.]]></description>
                <pubDate>Wed, 12 Sep 2024 10:30:00 GMT</pubDate>
                <guid>https://example.com/taiwan-cyber-security</guid>
                <author>Security Reporter</author>
                <category>Security</category>
                <category>Taiwan</category>
            </item>
            <item>
                <title>Tech Innovation: New AI Research Center Opens in Taipei</title>
                <link>https://example.com/ai-research-taipei</link>
                <description><![CDATA[A new artificial intelligence research center has been established in Taipei, focusing on developing cutting-edge AI technologies for various industrial applications.]]></description>
                <pubDate>Wed, 12 Sep 2024 08:15:00 GMT</pubDate>
                <guid>https://example.com/ai-research-taipei</guid>
                <author>Tech Correspondent</author>
                <category>Technology</category>
                <category>AI</category>
            </item>
        </channel>
    </rss>"""
    
    print("📄 Parsing sample RSS feed...")
    
    # Parse RSS content
    parser = RSSParser()
    items = parser.parse_feed(sample_rss, "https://demo.example.com/rss")
    
    print(f"✅ Found {len(items)} articles in feed")
    print()
    
    # Normalize each item
    normalizer = DataNormalizer()
    
    for i, item in enumerate(items, 1):
        print(f"📰 Article {i}: {item.title}")
        print(f"   🔗 URL: {item.link}")
        print(f"   👤 Author: {item.author}")
        print(f"   📅 Published: {item.published}")
        print(f"   🏷️  Categories: {', '.join(item.categories)}")
        print()
        
        # Normalize the article
        article = normalizer.normalize_item(item, "https://demo.example.com/rss")
        
        if article:
            print(f"   ✨ Normalized successfully")
            print(f"   🔤 Language: {article.language}")
            print(f"   🔍 Content hash: {article.content_hash}")
            print(f"   📝 Summary: {article.summary[:100]}...")
            
            # Demonstrate similarity detection
            if i == 1:
                first_hash = article.content_hash
            elif i == 2 and first_hash:
                similar = are_similar(first_hash, article.content_hash, threshold=10)
                print(f"   🔍 Similar to first article: {'Yes' if similar else 'No'}")
        else:
            print(f"   ❌ Normalization failed")
        
        print("-" * 50)
    
    print("🎯 Demo completed!")
    print()
    print("📊 Key Features Demonstrated:")
    print("   • RSS/Atom feed parsing")
    print("   • Content normalization and cleaning")
    print("   • Language detection")
    print("   • Content deduplication with SimHash")
    print("   • URL cleaning and validation")
    print("   • Date parsing and timezone handling")


if __name__ == "__main__":
    asyncio.run(demo_rss_parsing())