"""Layered part matching: exact number -> fuzzy number -> semantic (DESIGN.md §6, ADR-07).

This is the only place matching logic lives; ingest reuses it.
"""

from dataclasses import asdict, dataclass

from django.contrib.postgres.search import TrigramSimilarity
from pgvector.django import CosineDistance
from rapidfuzz import fuzz

from apps.ai import client as ai
from apps.catalog.models import Brand, PartNumber, Product
from apps.core.utils import normalize_part_no

EXACT, FUZZY, SEMANTIC = "exact", "fuzzy", "semantic"
METHOD_LABELS = {EXACT: "精确号码", FUZZY: "模糊号码", SEMANTIC: "语义匹配"}
TOP_N = 5
FUZZY_MIN_RATIO = 75
# Real embedding models put almost any two truck-part texts above ~0.5 cosine similarity,
# while the mock hashing embedding rarely does; scores are spread over [floor, 1].
SEMANTIC_FLOOR = 0.5
SEMANTIC_FLOOR_MOCK = 0.1


@dataclass
class Candidate:
    product_id: int
    score: int
    method: str
    matched_number: str = ""
    matched_type: str = ""
    note: str = ""

    def as_dict(self):
        return asdict(self)


def _active_numbers():
    return PartNumber.objects.exclude(product__status=Product.ARCHIVED).select_related("brand")


def strip_brand_prefix(raw: str) -> str:
    """"Knorr-Bremse K012345" / "MANN W 962/19" -> number without the brand word."""
    words = raw.strip().split()
    if len(words) < 2:
        return raw
    first = words[0].lower()
    for name in Brand.objects.values_list("name", flat=True):
        n = name.lower()
        if first == n or first == n.split("-")[0] or (len(first) >= 4 and n.startswith(first)):
            return " ".join(words[1:])
    return raw


def match_number(raw: str) -> list[Candidate]:
    query = normalize_part_no(raw)
    if len(query) < 3:
        return []
    exact = list(_active_numbers().filter(normalized=query))
    if not exact:
        stripped = strip_brand_prefix(raw)
        if stripped != raw:
            query = normalize_part_no(stripped)
            exact = list(_active_numbers().filter(normalized=query))
    results = [Candidate(pn.product_id, 100, EXACT, str(pn), pn.type) for pn in exact]
    if len(results) >= TOP_N or len(query) < 5:
        return results

    # pg_trgm "%" uses the GIN index to prefilter; rapidfuzz edit distance gives the final score,
    # because one wrong digit in an 8-digit number drops trigram similarity to ~0.5.
    seen = {c.product_id for c in results}
    similar = (
        _active_numbers()
        .filter(normalized__trigram_similar=query)
        .annotate(sim=TrigramSimilarity("normalized", query))
        .order_by("-sim")[:30]
    )
    fuzzy = []
    for pn in similar:
        if pn.product_id in seen:
            continue
        ratio = fuzz.ratio(query, pn.normalized)
        if ratio >= FUZZY_MIN_RATIO:
            fuzzy.append(Candidate(pn.product_id, round(80 + (ratio - FUZZY_MIN_RATIO) / (100 - FUZZY_MIN_RATIO) * 15), FUZZY, str(pn), pn.type))
    return results + sorted(fuzzy, key=lambda c: -c.score)


def match_text(text: str, category_hint: str | None = None) -> list[Candidate]:
    if not text.strip():
        return []
    vector = ai.embed([text], task="embed_query")[0]
    qs = (
        Product.objects.exclude(status=Product.ARCHIVED)
        .exclude(embedding=None)
        .annotate(distance=CosineDistance("embedding", vector))
        .order_by("distance")[:TOP_N]
    )
    floor = SEMANTIC_FLOOR_MOCK if ai.is_mock("embedding") else SEMANTIC_FLOOR
    results = []
    for product in qs:
        similarity = 1 - product.distance
        if similarity < floor:
            continue
        score = round(60 + (similarity - floor) / (1 - floor) * 20)
        results.append(Candidate(product.id, max(60, min(80, score)), SEMANTIC, note=f"相似度 {similarity:.2f}"))
    return results


def match_line(part_no: str | None = None, description: str = "", vehicle: str | None = None, weight: float = 1.0) -> list[Candidate]:
    candidates: dict[int, Candidate] = {}

    def add(items):
        for c in items:
            c.score = round(c.score * weight)
            if c.product_id not in candidates or candidates[c.product_id].score < c.score:
                candidates[c.product_id] = c

    if part_no:
        add(match_number(part_no))
    has_strong = any(c.method == EXACT for c in candidates.values())
    if not has_strong and (description or vehicle) and len(candidates) < TOP_N:
        add(match_text(" ".join(filter(None, [description, vehicle]))))
    return sorted(candidates.values(), key=lambda c: -c.score)[:TOP_N]
