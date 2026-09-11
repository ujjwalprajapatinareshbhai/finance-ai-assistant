import re


# ============================================================
# LOCAL SAFETY FILTER
# ============================================================

BLOCKED_PATTERNS = [

    r"\bhow to hack\b",
    r"\bhow do i hack\b",
    r"\bcreate malware\b",
    r"\bwrite malware\b",
    r"\bransomware\b",
    r"\bsteal passwords\b",
    r"\bsteal credentials\b",
    r"\bcredit card fraud\b",
    r"\bfinancial fraud\b",
    r"\bphishing attack\b",
]


def is_flagged(text: str) -> bool:

    if not text:
        return False

    text_lower = text.lower()

    for pattern in BLOCKED_PATTERNS:

        if re.search(pattern, text_lower):
            return True

    return False    