#!/usr/bin/env python3
"""
Test script for minimal SimHash utility.

Tests the core SimHash functions: tokenize, simhash, and hamming_distance.
"""

from newsbot.core.simhash import tokenize, simhash, hamming_distance, SimHash


def test_tokenize():
    """Test the tokenize function."""
    print("🔤 Testing tokenize function")
    print("-" * 30)
    
    test_cases = [
        ("Hello World! 123", ["hello", "world", "123"]),
        ("Testing-with_punctuation", ["testing", "with", "punctuation"]),
        ("Multiple   spaces\nand\twhitespace", ["multiple", "spaces", "and", "whitespace"]),
        ("MixedCASE text", ["mixedcase", "text"]),
        ("", []),
        ("123 456 789", ["123", "456", "789"]),
        ("Special chars: !@#$%^&*()", ["special", "chars"]),
    ]
    
    for text, expected in test_cases:
        result = tokenize(text)
        status = "✅" if result == expected else "❌"
        print(f"{status} Input: {repr(text)}")
        print(f"   Expected: {expected}")
        print(f"   Got: {result}")
        print()


def test_simhash():
    """Test the simhash function."""
    print("🔢 Testing simhash function")
    print("-" * 30)
    
    test_cases = [
        "The quick brown fox jumps over the lazy dog",
        "The quick brown fox jumps over the lazy dog",  # Same text
        "The quick brown fox jumped over the lazy dog",  # Similar text
        "Completely different text about technology news",
        "",  # Empty text
        "123 456 789",  # Numbers
        "a",  # Single character
    ]
    
    hashes = []
    for text in test_cases:
        hash_result = simhash(text)
        hashes.append(hash_result)
        print(f"Text: {repr(text)}")
        print(f"SimHash: {hash_result}")
        print(f"Length: {len(hash_result)} hex chars")
        print()
    
    # Test deterministic behavior
    print("🔄 Testing deterministic behavior:")
    hash1 = simhash("Test text for consistency")
    hash2 = simhash("Test text for consistency")
    print(f"Same text hashed twice: {hash1 == hash2}")
    
    # Test different bit sizes
    print("\n📏 Testing different bit sizes:")
    text = "Sample text for bit size testing"
    for bits in [32, 64, 128]:
        hash_result = simhash(text, bits)
        print(f"{bits} bits: {hash_result} (length: {len(hash_result)})")
    
    return hashes


def test_hamming_distance():
    """Test the hamming_distance function."""
    print("\n📐 Testing hamming_distance function")
    print("-" * 30)
    
    # Test with known values
    test_cases = [
        ("f", "f", 0),  # Identical
        ("f", "e", 1),  # 1111 vs 1110 = 1 bit difference
        ("ff", "00", 8),  # All bits different
        ("abc", "def", None),  # Different but unknown exact count
        ("123", "321", None),  # Different but unknown exact count
        ("", "f", None),  # Edge case
    ]
    
    for hex1, hex2, expected in test_cases:
        distance = hamming_distance(hex1, hex2)
        if expected is not None:
            status = "✅" if distance == expected else "❌"
            print(f"{status} hamming_distance('{hex1}', '{hex2}') = {distance} (expected {expected})")
        else:
            print(f"ℹ️ hamming_distance('{hex1}', '{hex2}') = {distance}")
    
    # Test with real SimHash results
    print("\n🎯 Testing with SimHash results:")
    text1 = "The quick brown fox"
    text2 = "The quick brown fox"  # Same
    text3 = "The quick brown dog"  # Similar
    text4 = "Completely different text"  # Different
    
    hash1 = simhash(text1)
    hash2 = simhash(text2)
    hash3 = simhash(text3)
    hash4 = simhash(text4)
    
    print(f"Text 1: {repr(text1)}")
    print(f"Text 2: {repr(text2)}")
    print(f"Distance: {hamming_distance(hash1, hash2)} (should be 0)")
    print()
    
    print(f"Text 1: {repr(text1)}")
    print(f"Text 3: {repr(text3)}")
    print(f"Distance: {hamming_distance(hash1, hash3)} (should be small)")
    print()
    
    print(f"Text 1: {repr(text1)}")
    print(f"Text 4: {repr(text4)}")
    print(f"Distance: {hamming_distance(hash1, hash4)} (should be large)")


def test_legacy_compatibility():
    """Test legacy SimHash class compatibility."""
    print("\n🔄 Testing legacy compatibility")
    print("-" * 30)
    
    text1 = "Sample text for testing"
    text2 = "Sample text for testing"  # Same
    text3 = "Different sample text"     # Different
    
    # Create SimHash objects
    sh1 = SimHash(text1)
    sh2 = SimHash(text2)
    sh3 = SimHash(text3)
    
    print(f"SimHash 1: {sh1}")
    print(f"SimHash 2: {sh2}")
    print(f"SimHash 3: {sh3}")
    print()
    
    print(f"Distance 1-2: {sh1.distance(sh2)} (should be 0)")
    print(f"Distance 1-3: {sh1.distance(sh3)} (should be > 0)")


def test_edge_cases():
    """Test edge cases and error conditions."""
    print("\n🚨 Testing edge cases")
    print("-" * 30)
    
    # Test empty and None inputs
    print("Empty text:")
    empty_hash = simhash("")
    print(f"  simhash(''): {empty_hash}")
    
    print("\nNone tokenization:")
    none_tokens = tokenize(None)
    print(f"  tokenize(None): {none_tokens}")
    
    print("\nInvalid hex strings:")
    try:
        distance = hamming_distance("invalid", "hex")
        print(f"  hamming_distance('invalid', 'hex'): {distance}")
    except Exception as e:
        print(f"  Exception: {e}")
    
    # Test very long text
    print("\nVery long text:")
    long_text = "word " * 1000
    long_hash = simhash(long_text)
    print(f"  Long text hash: {long_hash[:16]}... (length: {len(long_hash)})")


def main():
    """Run all tests."""
    print("🧪 Minimal SimHash Utility Tests")
    print("=" * 50)
    
    test_tokenize()
    hashes = test_simhash()
    test_hamming_distance()
    test_legacy_compatibility()
    test_edge_cases()
    
    print("\n✅ All tests completed!")
    print("\n📊 Summary:")
    print("   • tokenize(): Extracts alphanumeric lowercase tokens")
    print("   • simhash(): Returns deterministic hex string")
    print("   • hamming_distance(): Calculates bit differences")
    print("   • Legacy SimHash class maintained for compatibility")


if __name__ == "__main__":
    main()