import re


def extract_summary(content: str) -> str:
    """Extract text inside { } if present."""
    match = re.search(r"\{(.*?)\}", content)
    if match:
        return match.group(1).strip()
    return content.strip()