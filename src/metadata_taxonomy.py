from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from langchain_core.documents import Document


JOURNAL_CATEGORY_BY_CODE: dict[str, str] = {
    "AMJ": "organization_and_strategy",
    "AMR": "organization_and_strategy",
    "ASQ": "organization_and_strategy",
    "JOM": "organization_and_strategy",
    "SMJ": "organization_and_strategy",
    "ORGS": "organization_and_strategy",
    "ORSC": "operations_and_management",
    "JIBS": "international_business",
    "JMIS": "information_systems",
    "JBE": "ethics_and_sustainability",
    "RFS": "finance_and_economics",
    "RP": "innovation_and_policy",
    "ARXIV": "preprint",
}


JOURNAL_CATEGORY_LABELS: dict[str, str] = {
    "organization_and_strategy": "Organization & Strategy",
    "operations_and_management": "Operations & Management",
    "international_business": "International Business",
    "information_systems": "Information Systems",
    "ethics_and_sustainability": "Ethics & Sustainability",
    "finance_and_economics": "Finance & Economics",
    "innovation_and_policy": "Innovation & Policy",
    "preprint": "Preprint",
    "other": "Other",
}


SUBFIELD_KEYWORDS: dict[str, tuple[str, ...]] = {
    "platform_economy": (
        "platform",
        "ecosystem",
        "marketplace",
        "two-sided",
        "complementor",
        "sharing economy",
        "gig economy",
    ),
    "digital_finance": (
        "fintech",
        "digital finance",
        "blockchain",
        "crypto",
        "cryptocurrency",
        "payment",
        "lending",
        "bank",
        "credit",
        "mortgage",
        "loan",
        "financial crisis",
    ),
    "digital_governance_and_ai": (
        "artificial intelligence",
        "ai ",
        "algorithm",
        "machine learning",
        "automation",
        "data governance",
        "privacy",
        "ethic",
    ),
    "digital_transformation_and_is": (
        "digital transformation",
        "information system",
        "enterprise system",
        "database",
        "technostress",
        "it capability",
        "it adoption",
        "erp",
    ),
    "international_digital_business": (
        "internationalization",
        "multinational",
        "mne",
        "entry mode",
        "globalization",
        "institutional distance",
        "de-globalization",
    ),
    "innovation_and_entrepreneurship": (
        "innovation",
        "entrepreneurship",
        "startup",
        "dynamic capabilities",
        "absorptive capacity",
        "new venture",
    ),
    "sustainability_and_esg": (
        "esg",
        "csr",
        "sustainability",
        "social entrepreneurship",
        "carbon",
        "climate",
        "circular",
        "social good",
    ),
    "labor_and_employment": (
        "labor",
        "employment",
        "job",
        "worker",
        "wage",
        "human resource",
        "voice",
        "occupational",
    ),
}


SUBFIELD_LABELS: dict[str, str] = {
    "platform_economy": "Platform Economy",
    "digital_finance": "Digital Finance",
    "digital_governance_and_ai": "Digital Governance & AI",
    "digital_transformation_and_is": "Digital Transformation & IS",
    "international_digital_business": "International Digital Business",
    "innovation_and_entrepreneurship": "Innovation & Entrepreneurship",
    "sustainability_and_esg": "Sustainability & ESG",
    "labor_and_employment": "Labor & Employment",
    "other": "Other",
}


SUBFIELD_BY_JOURNAL_CATEGORY: dict[str, str] = {
    "information_systems": "digital_transformation_and_is",
    "finance_and_economics": "digital_finance",
    "ethics_and_sustainability": "sustainability_and_esg",
    "international_business": "international_digital_business",
}


YEAR_RE = re.compile(r"(19\d{2}|20\d{2}|2100)")


def _normalize_text(text: str) -> str:
    lowered = text.lower()
    lowered = lowered.replace("-", " ").replace("_", " ")
    lowered = re.sub(r"\s+", " ", lowered)
    return f" {lowered.strip()} "


def normalize_subfield(value: str) -> str:
    key = value.strip().lower().replace("-", "_").replace(" ", "_")
    return key if key in SUBFIELD_LABELS else "other"


def normalize_journal_category(value: str) -> str:
    key = value.strip().lower().replace("-", "_").replace(" ", "_")
    return key if key in JOURNAL_CATEGORY_LABELS else "other"


def normalize_journal_code(value: str) -> str:
    cleaned = re.sub(r"[^A-Z0-9]", "", value.strip().upper())
    return cleaned or "UNKNOWN"


def normalize_pub_year(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value if 1900 <= value <= 2100 else None
    text = str(value).strip()
    if not text:
        return None
    match = YEAR_RE.search(text)
    if not match:
        return None
    year = int(match.group(1))
    return year if 1900 <= year <= 2100 else None


def extract_journal_code(source: str) -> str:
    stem = Path(source).stem.upper()
    pattern_candidates = [
        r"^\d+_([A-Z]{2,10})_\d{4}(?:_|$)",
        r"^\d+_([A-Z]{2,10})(?:_|$)",
        r"^([A-Z]{2,10})_\d{4}(?:_|$)",
    ]
    for pattern in pattern_candidates:
        match = re.search(pattern, stem)
        if match:
            return normalize_journal_code(match.group(1))

    for token in re.split(r"[^A-Z]+", stem):
        if token in JOURNAL_CATEGORY_BY_CODE:
            return normalize_journal_code(token)
    return "UNKNOWN"


def infer_journal_category(journal_code: str) -> str:
    code = normalize_journal_code(journal_code)
    return JOURNAL_CATEGORY_BY_CODE.get(code, "other")


def extract_publication_year(source: str, published: str = "") -> int | None:
    year = normalize_pub_year(published)
    if year is not None:
        return year

    stem = Path(source).stem
    match = YEAR_RE.search(stem)
    if not match:
        return None
    parsed = int(match.group(1))
    return parsed if 1900 <= parsed <= 2100 else None


def infer_subfield(title: str, text: str, journal_category: str) -> str:
    title_norm = _normalize_text(title)
    text_norm = _normalize_text(text[:4000])

    best_subfield = "other"
    best_score = 0
    for subfield, keywords in SUBFIELD_KEYWORDS.items():
        score = 0
        for keyword in keywords:
            key = _normalize_text(keyword)
            if key in title_norm:
                score += 3
            elif key in text_norm:
                score += 1
        if score > best_score:
            best_score = score
            best_subfield = subfield

    if best_score > 0:
        return best_subfield
    return SUBFIELD_BY_JOURNAL_CATEGORY.get(journal_category, "other")


def enrich_metadata(
    metadata: Mapping[str, Any] | None,
    text: str = "",
) -> dict[str, Any]:
    raw = dict(metadata or {})
    source = str(raw.get("source", ""))
    title = str(raw.get("title", ""))
    raw_journal_code = str(raw.get("journal_code", "")).strip()
    journal_code = (
        normalize_journal_code(raw_journal_code)
        if raw_journal_code
        else extract_journal_code(source)
    )
    published = str(raw.get("published", "")).strip()
    pub_year = normalize_pub_year(raw.get("pub_year"))
    if pub_year is None:
        pub_year = extract_publication_year(source, published)
    journal_category = normalize_journal_category(
        str(raw.get("journal_category", "")) or infer_journal_category(journal_code)
    )
    subfield = normalize_subfield(
        str(raw.get("subfield", "")) or infer_subfield(title, text, journal_category)
    )

    raw["journal_code"] = journal_code
    raw["journal_category"] = journal_category
    raw["subfield"] = subfield
    raw["published"] = published
    raw["pub_year"] = pub_year
    return raw


def enrich_document_metadata(doc: Document) -> Document:
    doc.metadata = enrich_metadata(doc.metadata, text=doc.page_content)
    return doc


def list_supported_subfields() -> list[str]:
    return [k for k in SUBFIELD_LABELS.keys() if k != "other"]


def list_supported_journal_categories() -> list[str]:
    return [k for k in JOURNAL_CATEGORY_LABELS.keys() if k != "other"]


def list_supported_journal_codes() -> list[str]:
    codes = sorted(JOURNAL_CATEGORY_BY_CODE.keys())
    return codes + ["UNKNOWN"]


def subfield_label(subfield: str) -> str:
    return SUBFIELD_LABELS.get(normalize_subfield(subfield), subfield)


def journal_category_label(category: str) -> str:
    return JOURNAL_CATEGORY_LABELS.get(normalize_journal_category(category), category)
