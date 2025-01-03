from typing import List

def is_palindrome(text: str) -> bool:
    """Check if a string is a palindrome."""
    cleaned = ''.join(c.lower() for c in text if c.isalnum())
    return cleaned == cleaned[::-1]

def find_duplicates(items: List[str]) -> List[str]:
    """Find duplicate items in a list."""
    seen = set()
    duplicates = []
    for item in items:
        if item in seen:
            duplicates.append(item)
        seen.add(item)
    return duplicates
