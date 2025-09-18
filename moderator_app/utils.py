import re
import hashlib
from django.core.cache import cache

def extract_summary(content):
    bracket_match = re.search(r'\{([^}]+)\}', content)
    if bracket_match:
        summary = bracket_match.group(1).strip()
        words = summary.split()
        if len(words) <= 10:
            return summary
    words = content.strip().split()[:8]
    return ' '.join(words)


def hash_comment(text):
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", "", text).strip()
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

