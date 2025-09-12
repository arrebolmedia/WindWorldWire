"""Minimal SimHash utility for content similarity detection."""

import hashlib
import re
from typing import List


def tokenize(text: str) -> List[str]:
    """
    Tokenize text into alphanumeric lowercase tokens.
    
    Args:
        text: Input text to tokenize
        
    Returns:
        List of lowercase alphanumeric tokens
    """
    if not text:
        return []
    
    # Convert to lowercase and extract alphanumeric words
    text = text.lower()
    # Replace all non-alphanumeric characters with spaces, then split
    text = re.sub(r'[^a-z0-9]', ' ', text)
    tokens = text.split()
    
    # Filter out empty tokens
    return [token for token in tokens if token]


def simhash(text: str, bits: int = 64) -> str:
    """
    Compute SimHash for text and return as hex string.
    
    Args:
        text: Input text
        bits: Number of bits in hash (default 64)
        
    Returns:
        SimHash as hex string
    """
    if not text:
        return "0" * (bits // 4)  # Return zero hash for empty text
    
    # Tokenize text
    tokens = tokenize(text)
    
    if not tokens:
        return "0" * (bits // 4)
    
    # Initialize bit vector
    v = [0] * bits
    
    # Process each token
    for token in tokens:
        # Hash token to get fingerprint
        token_hash = int(hashlib.md5(token.encode('utf-8')).hexdigest(), 16)
        
        # Update bit vector
        for i in range(bits):
            bit = (token_hash >> i) & 1
            if bit:
                v[i] += 1
            else:
                v[i] -= 1
    
    # Convert to final hash
    result = 0
    for i in range(bits):
        if v[i] > 0:
            result |= (1 << i)
    
    # Return as hex string with appropriate padding
    hex_digits = bits // 4
    return f"{result:0{hex_digits}x}"


def hamming_distance(hex1: str, hex2: str) -> int:
    """
    Calculate Hamming distance between two hex strings.
    
    Args:
        hex1: First hex string
        hex2: Second hex string
        
    Returns:
        Hamming distance (number of differing bits)
    """
    try:
        # Convert hex strings to integers
        int1 = int(hex1, 16)
        int2 = int(hex2, 16)
        
        # XOR and count set bits
        xor = int1 ^ int2
        return bin(xor).count('1')
        
    except ValueError:
        # Invalid hex strings
        return float('inf')


# Legacy compatibility classes
class SimHash:
    """Legacy SimHash class for backward compatibility."""
    
    def __init__(self, text: str, f: int = 64):
        """Initialize SimHash with text."""
        self.f = f
        self.hash_str = simhash(text, f)
        self.hash = int(self.hash_str, 16)
    
    def distance(self, other: 'SimHash') -> int:
        """Calculate Hamming distance to another SimHash."""
        return hamming_distance(self.hash_str, other.hash_str)
    
    def __str__(self) -> str:
        """Return hash as hex string."""
        return self.hash_str