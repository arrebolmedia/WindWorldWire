#!/usr/bin/env python3
"""
Minimal SimHash Utility Demo

Demonstrates the three core functions:
- tokenize(): Extract alphanumeric lowercase tokens
- simhash(): Generate deterministic hex string hash
- hamming_distance(): Calculate bit differences between hashes
"""

from newsbot.core.simhash import tokenize, simhash, hamming_distance


def demo_tokenize():
    """Demonstrate the tokenize function."""
    print("🔤 tokenize() - Extract alphanumeric lowercase tokens")
    print("-" * 50)
    
    examples = [
        "The Quick Brown Fox!",
        "Hello, World! How are you?",
        "Testing-with_various@punctuation#marks",
        "Mixed123Numbers456And789Text",
        "   Multiple   spaces   and   tabs   ",
        "🚀 Unicode and émojis and ñoño",
    ]
    
    for text in examples:
        tokens = tokenize(text)
        print(f"Input:  {repr(text)}")
        print(f"Tokens: {tokens}")
        print()


def demo_simhash():
    """Demonstrate the simhash function."""
    print("🔢 simhash() - Generate deterministic hex string hash")
    print("-" * 50)
    
    examples = [
        "This is a sample news article about technology",
        "This is a sample news article about technology",  # Exact duplicate
        "This is a sample news article about tech",        # Very similar
        "This is a sample article about technology news",  # Similar but reordered
        "This is a completely different article about sports", # Different topic
        "",  # Empty
        "Short",  # Very short
        "A" * 1000,  # Very long
    ]
    
    hashes = []
    for i, text in enumerate(examples):
        hash_result = simhash(text)
        hashes.append(hash_result)
        print(f"Text {i+1}: {repr(text[:50] + '...' if len(text) > 50 else text)}")
        print(f"Hash:   {hash_result}")
        print()
    
    return hashes


def demo_hamming_distance(hashes):
    """Demonstrate the hamming_distance function."""
    print("📐 hamming_distance() - Calculate bit differences")
    print("-" * 50)
    
    # Compare different text combinations
    comparisons = [
        (0, 1, "Identical texts"),
        (0, 2, "Very similar texts"),
        (0, 3, "Similar but reordered"),
        (0, 4, "Different topics"),
        (2, 3, "Similar vs reordered"),
        (4, 5, "Different vs empty"),
    ]
    
    for i, j, description in comparisons:
        if i < len(hashes) and j < len(hashes):
            distance = hamming_distance(hashes[i], hashes[j])
            print(f"{description}:")
            print(f"  Hash {i+1}: {hashes[i]}")
            print(f"  Hash {j+1}: {hashes[j]}")
            print(f"  Distance: {distance} bits")
            
            # Interpret similarity
            if distance == 0:
                similarity = "Identical"
            elif distance <= 3:
                similarity = "Very similar"
            elif distance <= 10:
                similarity = "Similar"
            elif distance <= 20:
                similarity = "Somewhat similar"
            else:
                similarity = "Different"
            
            print(f"  Similarity: {similarity}")
            print()


def demo_practical_use_case():
    """Demonstrate practical use case for duplicate detection."""
    print("🎯 Practical Use Case - News Article Duplicate Detection")
    print("-" * 60)
    
    # Simulate news articles
    articles = [
        {
            "id": 1,
            "title": "Breaking: New Technology Breakthrough Announced",
            "content": "Scientists at major university have announced a breakthrough in quantum computing technology that could revolutionize the industry."
        },
        {
            "id": 2,
            "title": "BREAKING: New Technology Breakthrough Announced",
            "content": "Scientists at a major university have announced a breakthrough in quantum computing technology that could revolutionize the industry."
        },
        {
            "id": 3,
            "title": "Quantum Computing Breakthrough at University",
            "content": "Researchers announced significant advances in quantum computing that may transform the technology sector."
        },
        {
            "id": 4,
            "title": "Sports Update: Championship Finals Tonight",
            "content": "The championship finals will take place tonight with two top teams competing for the title."
        }
    ]
    
    # Generate SimHashes for each article
    article_hashes = []
    for article in articles:
        content = f"{article['title']} {article['content']}"
        hash_result = simhash(content)
        article_hashes.append(hash_result)
        
        print(f"Article {article['id']}: {article['title'][:40]}...")
        print(f"SimHash: {hash_result}")
        print()
    
    # Find potential duplicates
    print("🔍 Duplicate Detection Results:")
    print("-" * 40)
    
    threshold = 10  # Bits difference threshold for "similar"
    
    for i in range(len(articles)):
        for j in range(i + 1, len(articles)):
            distance = hamming_distance(article_hashes[i], article_hashes[j])
            
            if distance <= threshold:
                print(f"📄 Articles {articles[i]['id']} and {articles[j]['id']} are similar:")
                print(f"   Distance: {distance} bits")
                print(f"   Article {articles[i]['id']}: {articles[i]['title'][:50]}...")
                print(f"   Article {articles[j]['id']}: {articles[j]['title'][:50]}...")
                
                if distance <= 3:
                    print("   ⚠️  Potential duplicate!")
                elif distance <= 10:
                    print("   💡 Similar content")
                print()


def demo_different_bit_sizes():
    """Demonstrate different bit sizes for SimHash."""
    print("📏 Different Bit Sizes - Trade-offs")
    print("-" * 40)
    
    text = "Sample text for testing different SimHash bit sizes and their characteristics"
    
    bit_sizes = [16, 32, 64, 128]
    
    for bits in bit_sizes:
        hash_result = simhash(text, bits)
        print(f"{bits:3d} bits: {hash_result}")
        print(f"        Length: {len(hash_result)} hex characters")
        print(f"        Storage: {len(hash_result)} bytes as string")
        print()
    
    print("💡 Recommendations:")
    print("   • 16 bits: Fast, minimal storage, less precision")
    print("   • 32 bits: Good balance for small datasets")
    print("   • 64 bits: Standard choice for most applications")
    print("   • 128 bits: High precision for large datasets")


def main():
    """Run all demonstrations."""
    print("🧪 Minimal SimHash Utility Demo")
    print("=" * 60)
    print()
    
    demo_tokenize()
    hashes = demo_simhash()
    demo_hamming_distance(hashes)
    demo_practical_use_case()
    demo_different_bit_sizes()
    
    print("✅ Demo completed!")
    print("\n📋 Summary of Functions:")
    print("   • tokenize(text) → List[str]")
    print("     Extracts alphanumeric lowercase tokens")
    print("   • simhash(text, bits=64) → str")
    print("     Returns deterministic hex string hash")
    print("   • hamming_distance(hex1, hex2) → int")
    print("     Calculates bit differences between hashes")
    print()
    print("🎯 Key Features:")
    print("   • Minimal and deterministic")
    print("   • Fast tokenization and hashing")
    print("   • Configurable bit sizes")
    print("   • Suitable for duplicate detection")
    print("   • Legacy compatibility maintained")


if __name__ == "__main__":
    main()