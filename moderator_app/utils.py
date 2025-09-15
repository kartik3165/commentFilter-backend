import re


def extract_summary(content):
    """
    Extract summary from the model response.
    Looks for content within {} brackets, falls back to first 8 words.
    """
    import re
    
    # Try to extract content within {} brackets
    bracket_match = re.search(r'\{([^}]+)\}', content)
    if bracket_match:
        summary = bracket_match.group(1).strip()
        # Ensure it's roughly 8 words
        words = summary.split()
        if len(words) <= 10:  # Allow some flexibility
            return summary
    
    # Fallback: take first 8 words and clean up
    words = content.strip().split()[:8]
    return ' '.join(words)