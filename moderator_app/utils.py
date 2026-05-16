import re
import hashlib
from django.core.cache import cache


def extract_summary(content: str) -> str:
    # LLM is prompted to return summary inside <summary></summary>
    tag_match = re.search(r'<summary>(.*?)</summary>', content, re.IGNORECASE | re.DOTALL)
    if tag_match:
        summary = tag_match.group(1).strip()
        words = summary.split()
        if words:
            return ' '.join(words[:8])

    # Legacy fallback: {} brackets
    bracket_match = re.search(r'\{([^}]+)\}', content)
    if bracket_match:
        summary = bracket_match.group(1).strip()
        words = summary.split()
        if words and len(words) <= 10:
            return ' '.join(words[:8])

    # Final fallback: first 8 words of raw content
    words = content.strip().split()[:8]
    return ' '.join(words)


def parse_tone_integer(content: str) -> int:
    stripped = content.strip()
    # Accept a single digit or a digit optionally followed by non-digit chars
    match = re.search(r'\b([1-9]|10|11)\b', stripped)
    if match:
        return int(match.group(1))
    raise ValueError(f"Could not extract tone integer (1-11) from: {stripped!r}")


def hash_comment(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", "", text).strip()
    return hashlib.sha256(text.encode('utf-8')).hexdigest()
