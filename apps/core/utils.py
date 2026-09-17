import re
import unicodedata

# Separators customers and suppliers put inside part numbers.
_SEPARATORS = re.compile(r"[\s\-./_\\]+")
# Noise prefixes such as "OE:", "OEM NO.", "Ref." written before the number.
_PREFIX = re.compile(r"^(?:OEM?|REF|PART|P/N|PN|NO|NR)\s*(?:NO|NR|NUMBER)?\s*[.:#]*\s*", re.I)
_PART_TOKEN = re.compile(r"[A-Za-z]{0,3}[\s\-.]?\d[\d\s\-./A-Za-z]{2,}\d|[A-Za-z]{1,3}\s?\d{3,}")


def normalize_part_no(value: str | None) -> str:
    """Canonical form of a part number used for matching (DESIGN.md §5).

    Full-width to half-width, drop noise prefixes and separators, upper-case.
    Leading letters (Mercedes "A") and leading zeros are significant and kept.
    """
    if not value:
        return ""
    s = unicodedata.normalize("NFKC", str(value)).strip()
    s = _PREFIX.sub("", s)
    s = _SEPARATORS.sub("", s)
    return s.upper()


def split_numbers(value) -> list[str]:
    """Split a cell like "20837792 / 21122012; 8510-2011" into individual numbers."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        items = [str(v) for v in value]
    else:
        items = re.split(r"[,;，；\n|]+|\s/\s", str(value))
    return [i.strip() for i in items if i and normalize_part_no(i)]


def looks_like_part_number(token: str) -> bool:
    n = normalize_part_no(token)
    return len(n) >= 4 and sum(c.isdigit() for c in n) >= 3
