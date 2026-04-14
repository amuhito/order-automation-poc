import re
from typing import Any


MATERIAL_ALIASES = {
    "SUS304": ["SUS304", "SUS 304", "SUS-304"],
    "SUS316": ["SUS316", "SUS 316", "SUS-316"],
    "SS400": ["SS400", "SS 400", "SS-400"],
    "S45C": ["S45C", "S 45 C"],
    "SPCC": ["SPCC"],
    "A5052": ["A5052", "A 5052", "AL5052", "A5052P"],
    "SKD11": ["SKD11", "SKD 11"],
}

SURFACE_ALIASES = {
    "\u9ed2\u67d3\u3081": ["\u9ed2\u67d3\u3081", "\u30af\u30ed\u30be\u30e1", "BLACK OXIDE"],
    "\u30e1\u30c3\u30ad": ["\u30e1\u30c3\u30ad", "\u3081\u3063\u304d", "PLATING"],
    "\u4e9c\u925b\u30e1\u30c3\u30ad": ["\u4e9c\u925b\u30e1\u30c3\u30ad", "\u30e6\u30cb\u30af\u30ed", "\u4e09\u4fa1\u30af\u30ed\u30e1\u30fc\u30c8", "ZINC PLATING"],
    "\u7121\u96fb\u89e3\u30cb\u30c3\u30b1\u30eb": ["\u7121\u96fb\u89e3\u30cb\u30c3\u30b1\u30eb", "ENP", "ELECTROLESS NICKEL"],
    "\u30a2\u30eb\u30de\u30a4\u30c8": ["\u30a2\u30eb\u30de\u30a4\u30c8", "ANODIZE", "ANODIZING"],
    "\u5857\u88c5": ["\u5857\u88c5", "PAINT", "PAINTING"],
}

MATERIAL_LOOKUP = {
    alias.upper(): canonical
    for canonical, aliases in MATERIAL_ALIASES.items()
    for alias in aliases
}

SURFACE_LOOKUP = {
    alias.upper(): canonical
    for canonical, aliases in SURFACE_ALIASES.items()
    for alias in aliases
}

PART_NUMBER_CONTEXT_PATTERNS = [
    r"(?:\u56f3\u756a|\u56f3\u9762\u756a\u53f7|\u54c1\u756a|\u90e8\u756a|PART\s*NO\.?|PART\s*NUMBER|DRAWING\s*NO\.?)\s*[:\uFF1A]?\s*([A-Z0-9][A-Z0-9\-]{4,20})",
    r"\b([A-Z]{1,4}\d{2,}[A-Z0-9\-]{1,12})\b",
]

QUANTITY_PATTERNS = [
    r"(?:\u6570\u91cf|\u500b\u6570|QTY)\s*[:\uFF1A]?\s*([1-9]\d{0,5})\b",
    r"\b([1-9]\d{0,5})\s*(?:PCS|PC|\u500b|\u30f6|EA|SET)\b",
]

MATERIAL_CONTEXT_PATTERNS = [
    r"(?:\u6750\u8cea|\u6750\u6599|MATERIAL)\s*[:\uFF1A]?\s*([A-Z0-9\- ]{3,20})",
]

SURFACE_CONTEXT_PATTERNS = [
    r"(?:\u8868\u9762\u51e6\u7406|\u8868\u9762|SURFACE(?:\s*TREATMENT)?)\s*[:\uFF1A]?\s*([A-Z0-9\u3041-\u3093\u30a1-\u30f6\u4e00-\u9faf\- ]{2,40})",
]

NOISE_TOKENS = {
    "QTY",
    "PART",
    "NO",
    "MATERIAL",
    "SURFACE",
    "TREATMENT",
    "DRAWING",
    "PAGE",
    "SIZE",
    "DATE",
}


def parse_procurement_fields(text: str, history_records: list[dict[str, Any]] | None = None) -> dict:
    normalized = normalize_text(text)
    history_records = history_records or []

    part_number, part_score, part_source = extract_part_number(normalized, history_records)
    quantity, quantity_score, quantity_source = extract_quantity(normalized, history_records, part_number)
    material, material_score, material_source = extract_material(normalized, history_records, part_number)
    surface, surface_score, surface_source = extract_surface(normalized, history_records, part_number)
    supplier_candidate = find_supplier_candidate(history_records, part_number)

    field_scores = [part_score, quantity_score, material_score, surface_score]
    confidence = round(sum(field_scores) / len(field_scores), 2) if any(field_scores) else None

    return {
        "part_number": part_number,
        "quantity": quantity,
        "material": material,
        "surface": surface,
        "confidence": confidence,
        "supplier_candidate": supplier_candidate,
        "matched_history_count": count_part_matches(history_records, part_number),
        "evidence": {
            "part_number": {"source": part_source, "score": part_score},
            "quantity": {"source": quantity_source, "score": quantity_score},
            "material": {"source": material_source, "score": material_score},
            "surface": {"source": surface_source, "score": surface_score},
        },
        "raw_preview": normalized[:500],
    }


def normalize_text(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n").replace("\uFF1A", ":")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    return cleaned


def extract_part_number(text: str, history_records: list[dict[str, Any]]) -> tuple[str | None, float, str]:
    for pattern in PART_NUMBER_CONTEXT_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            candidate = cleanup_token(match.group(1))
            if is_valid_part_number(candidate):
                return candidate, 0.95 if "PART" in pattern or "DRAWING" in pattern else 0.9, "regex"

    ranked = rank_free_tokens(text)
    if ranked:
        candidate = ranked[0]
        history_hit = next((row for row in history_records if normalize_token(row.get("part_number")) == candidate), None)
        if history_hit:
            return candidate, 0.88, "history+regex"
        return candidate, 0.72, "regex"

    return None, 0.0, "none"


def extract_quantity(
    text: str,
    history_records: list[dict[str, Any]],
    part_number: str | None,
) -> tuple[int | None, float, str]:
    for pattern in QUANTITY_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return int(match.group(1)), 0.92, "regex"

    history_match = find_history_match(history_records, part_number)
    if history_match and history_match.get("quantity") is not None:
        return int(history_match["quantity"]), 0.55, "history"

    return None, 0.0, "none"


def extract_material(
    text: str,
    history_records: list[dict[str, Any]],
    part_number: str | None,
) -> tuple[str | None, float, str]:
    for pattern in MATERIAL_CONTEXT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            candidate = canonicalize_material(match.group(1))
            if candidate:
                return candidate, 0.94, "regex+dictionary"

    for alias, canonical in MATERIAL_LOOKUP.items():
        if alias in text.upper():
            return canonical, 0.82, "dictionary"

    history_match = find_history_match(history_records, part_number)
    if history_match and history_match.get("material"):
        return history_match["material"], 0.6, "history"

    return None, 0.0, "none"


def extract_surface(
    text: str,
    history_records: list[dict[str, Any]],
    part_number: str | None,
) -> tuple[str | None, float, str]:
    for pattern in SURFACE_CONTEXT_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            candidate = canonicalize_surface(match.group(1))
            if candidate:
                return candidate, 0.9, "regex+dictionary"

    for alias, canonical in SURFACE_LOOKUP.items():
        if alias in text.upper():
            return canonical, 0.78, "dictionary"

    history_match = find_history_match(history_records, part_number)
    if history_match and history_match.get("surface"):
        return history_match["surface"], 0.58, "history"

    return None, 0.0, "none"


def canonicalize_material(raw: str) -> str | None:
    cleaned = (cleanup_token(raw) or "").replace(" ", "")
    return MATERIAL_LOOKUP.get(cleaned.upper())


def canonicalize_surface(raw: str) -> str | None:
    cleaned = (cleanup_token(raw) or "").replace(" ", "")
    upper = cleaned.upper()
    for alias, canonical in SURFACE_LOOKUP.items():
        if alias.replace(" ", "") in upper:
            return canonical
    return None


def find_history_match(history_records: list[dict[str, Any]], part_number: str | None) -> dict[str, Any] | None:
    normalized_part = normalize_token(part_number)
    if not normalized_part:
        return None

    for row in history_records:
        if normalize_token(row.get("part_number")) == normalized_part:
            return row
    return None


def find_supplier_candidate(history_records: list[dict[str, Any]], part_number: str | None) -> str | None:
    history_match = find_history_match(history_records, part_number)
    if history_match and history_match.get("supplier_name"):
        return history_match["supplier_name"]
    return None


def count_part_matches(history_records: list[dict[str, Any]], part_number: str | None) -> int:
    normalized_part = normalize_token(part_number)
    if not normalized_part:
        return 0
    return sum(1 for row in history_records if normalize_token(row.get("part_number")) == normalized_part)


def rank_free_tokens(text: str) -> list[str]:
    tokens = re.findall(r"\b[A-Z0-9][A-Z0-9\-]{4,20}\b", text.upper())
    scored: list[tuple[float, str]] = []
    for token in tokens:
        if not is_valid_part_number(token):
            continue
        score = 0.0
        if any(char.isalpha() for char in token) and any(char.isdigit() for char in token):
            score += 0.45
        if "-" not in token:
            score += 0.1
        if 6 <= len(token) <= 12:
            score += 0.2
        if token not in NOISE_TOKENS:
            score += 0.15
        score += min(sum(1 for ch in token if ch.isdigit()), 4) * 0.02
        scored.append((score, token))

    scored.sort(reverse=True)
    return [token for _, token in scored[:5]]


def is_valid_part_number(token: str | None) -> bool:
    if not token:
        return False
    upper = token.upper()
    if upper in NOISE_TOKENS:
        return False
    if len(upper) < 5 or len(upper) > 20:
        return False
    if not re.fullmatch(r"[A-Z0-9\-]+", upper):
        return False
    if not any(ch.isalpha() for ch in upper):
        return False
    if not any(ch.isdigit() for ch in upper):
        return False
    return True


def cleanup_token(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().strip(":").strip()
    cleaned = re.sub(r"[^A-Za-z0-9\u3041-\u3093\u30a1-\u30f6\u4e00-\u9faf\-\s]", "", cleaned)
    return cleaned or None


def normalize_token(value: str | None) -> str | None:
    cleaned = cleanup_token(value)
    if not cleaned:
        return None
    return cleaned.replace(" ", "").upper()
