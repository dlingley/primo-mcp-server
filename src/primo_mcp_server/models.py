"""Pydantic models for Primo PNX response data.

Primo's API returns inconsistent field shapes -- the same field may be
a string, a list of strings, or missing entirely. These models normalise
everything into predictable types.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, field_validator


def _to_list(v: str | list[str] | None) -> list[str]:
    """Normalise a field that may be str, list[str], or None into list[str]."""
    if v is None:
        return []
    if isinstance(v, str):
        return [v]
    return list(v)


def _first_or_empty(v: str | list[str] | None) -> str:
    """Extract the first element, or return empty string."""
    items = _to_list(v)
    return items[0] if items else ""


# MARC relator terms that Primo appends to display names, e.g.
# "Mueller, John, 1958- author." -- stripped for clean author display.
_RELATORS = (
    "joint author", "issuing body", "edited by", "author", "authors",
    "editor", "editors", "narrator", "translator", "translators",
    "illustrator", "compiler", "contributor", "writer", "interviewer",
    "interviewee", "performer", "director", "producer", "composer",
    "photographer",
)
# Require the trailing period that Primo always appends ("author.", "editor."),
# so a genuine name segment that happens to be a relator word is left intact.
_RELATOR_RE = re.compile(
    r"[,\s]+(?:" + "|".join(re.escape(r) for r in _RELATORS) + r")\.\s*$",
    re.IGNORECASE,
)
_SUBFIELD_RE = re.compile(r"\$\$([A-Za-z])([^$]*)")
_VALUE_SEPARATORS_RE = re.compile(r"[;\uff1b]")


def _strip_subfields(value: str) -> str:
    """Drop Primo PNX '$$X' subfield codes, returning the human display text.

    Primo encodes subfields as '<display>$$Q<normalised>$$...'. The display
    text precedes the first '$$'; purely coded values fall back to the
    $$Q/$$V subfield content.
    """
    if not value or "$$" not in value:
        return value.strip() if value else ""
    head = value.split("$$", 1)[0].strip()
    if head:
        return head
    matches = _SUBFIELD_RE.findall(value)
    for preferred in ("N", "Q", "V", "a", "T", "L", "F"):
        for code, text in matches:
            if code == preferred and text.strip():
                return text.strip()
    for _code, text in matches:
        if text.strip():
            return text.strip()
    return value.strip()


def _clean_names(
    raw_values: list[str],
    *,
    split: bool = True,
    strip_relators: bool = True,
) -> list[str]:
    """Normalise name fields.

    For display.creator/contributor (split=True, strip_relators=True) this
    splits semicolon-joined entries and removes PNX subfield codes ($$Q...)
    and trailing MARC relator terms. For the already-clean structured
    addata.au/addau lists, pass split=False, strip_relators=False so only
    defensive subfield stripping is applied.
    """
    names: list[str] = []
    for raw in raw_values:
        base = _strip_subfields(raw)
        for part in (_VALUE_SEPARATORS_RE.split(base) if split else [base]):
            name = part.strip()
            if strip_relators:
                name = _RELATOR_RE.sub("", name)
            name = name.strip().rstrip(",").strip()
            if name:
                names.append(name)
    return names


class PrimoRecord(BaseModel):
    """A normalised Primo catalogue record."""

    # Identity
    record_id: str = ""
    source_id: str = ""
    source_system: str = ""

    # Display
    title: str = ""
    resource_type: str = ""
    language: str = ""
    creators: list[str] = []
    contributors: list[str] = []
    publisher: str = ""
    creation_date: str = ""
    source_label: str = ""
    description: str = ""
    snippet: str = ""
    subjects: list[str] = []
    keywords: list[str] = []
    is_part_of: str = ""

    # Identifiers
    identifiers: list[str] = []
    doi: str = ""
    isbn: list[str] = []
    issn: list[str] = []

    # Academic data
    journal_title: str = ""
    volume: str = ""
    issue: str = ""
    start_page: str = ""
    end_page: str = ""
    peer_reviewed: bool = False
    ris_type: str = ""
    authors_structured: list[str] = []
    additional_authors: list[str] = []

    # Availability
    fulltext_available: bool = False
    delivery_category: str = ""

    # Relevance
    score: float = 0.0
    context: str = ""

    @classmethod
    def from_api_doc(cls, doc: dict) -> PrimoRecord:
        """Parse a single document from the Primo /pnxs response."""
        pnx = doc.get("pnx", {})
        display = pnx.get("display", {})
        control = pnx.get("control", {})
        addata = pnx.get("addata", {})
        search = pnx.get("search", {})
        delivery = pnx.get("delivery", {})

        # Extract DOI from identifiers
        doi = ""
        identifiers = _to_list(display.get("identifier"))
        for ident in identifiers:
            if "DOI:" in ident.upper():
                doi = ident.split("DOI:")[-1].strip()
                break

        # Parse creators -- display.creator is often a single semicolon-separated
        # string and carries $$ subfield codes plus trailing relator terms.
        creators = _clean_names(_to_list(display.get("creator")))

        # Subjects -- may be semicolon-separated
        raw_subjects = _to_list(display.get("subject"))
        subjects = []
        for s in raw_subjects:
            for part in _VALUE_SEPARATORS_RE.split(s):
                p = _strip_subfields(part)
                if p:
                    subjects.append(p)

        # Keywords
        raw_keywords = _to_list(display.get("keyword"))
        keywords = []
        for k in raw_keywords:
            for part in _VALUE_SEPARATORS_RE.split(k):
                p = _strip_subfields(part)
                if p:
                    keywords.append(p)

        # Peer review
        lds50 = _to_list(display.get("lds50"))
        peer_reviewed = any("peer_review" in x.lower() for x in lds50)

        # Score
        score_raw = _to_list(control.get("score"))
        try:
            score = float(score_raw[0]) if score_raw else 0.0
        except (ValueError, IndexError):
            score = 0.0

        return cls(
            record_id=_first_or_empty(control.get("recordid")),
            source_id=_first_or_empty(control.get("sourceid")) or _first_or_empty(
                control.get("sourceid") if isinstance(control.get("sourceid"), str)
                else (control.get("sourceid", [None]) or [None])[0]
            ),
            source_system=_first_or_empty(control.get("sourcesystem")),
            title=_strip_subfields(_first_or_empty(display.get("title"))),
            resource_type=_first_or_empty(display.get("type")),
            language=_first_or_empty(display.get("language")),
            creators=creators,
            contributors=_clean_names(_to_list(display.get("contributor"))),
            publisher=_strip_subfields(_first_or_empty(display.get("publisher"))),
            creation_date=_first_or_empty(display.get("creationdate"))
                or _first_or_empty(addata.get("date")),
            source_label=_first_or_empty(display.get("source")),
            description=_first_or_empty(display.get("description"))
                or _first_or_empty(addata.get("abstract")),
            snippet=_first_or_empty(display.get("snippet")),
            subjects=subjects,
            keywords=keywords,
            is_part_of=_strip_subfields(_first_or_empty(display.get("ispartof"))),
            identifiers=identifiers,
            doi=doi,
            isbn=_to_list(addata.get("isbn")),
            issn=_to_list(addata.get("issn")),
            journal_title=_strip_subfields(_first_or_empty(addata.get("jtitle"))),
            volume=_first_or_empty(addata.get("volume")),
            issue=_first_or_empty(addata.get("issue")),
            start_page=_first_or_empty(addata.get("spage")),
            end_page=_first_or_empty(addata.get("epage")),
            peer_reviewed=peer_reviewed,
            ris_type=_first_or_empty(addata.get("ristype")),
            authors_structured=_clean_names(
                _to_list(addata.get("au")), split=False, strip_relators=False
            ),
            additional_authors=_clean_names(
                _to_list(addata.get("addau")), split=False, strip_relators=False
            ),
            fulltext_available="fulltext" in str(delivery.get("fulltext", "")),
            delivery_category=_first_or_empty(delivery.get("delcategory")),
            score=score,
            context=doc.get("context", ""),
        )

    @property
    def display_authors(self) -> list[str]:
        """Best available author list, in order of preference.

        Primo splits names across several fields: structured authors
        (addata.au) and additional authors/editors (addata.addau) are clean,
        while display.creator/contributor carry subfield noise. Falling back
        through them avoids "Unknown author" when only an edited-book editor
        list (addau) or a contributor is present.
        """
        return (
            self.authors_structured
            or self.additional_authors
            or self.creators
            or self.contributors
        )

    @property
    def year(self) -> str:
        """Four-digit year extracted from creation_date.

        Primo dates come in many shapes -- "2021", "2021-03", "c1996",
        "[2019]" -- so the first run of four digits is taken rather than a
        naive slice (which turned "c1996" into "c199").
        """
        m = re.search(r"\d{4}", self.creation_date)
        return m.group(0) if m else ""


class SearchInfo(BaseModel):
    """Pagination and total count info from a search response."""

    total: int = 0
    total_local: int = 0
    total_pc: int = 0
    first: int = 0
    last: int = 0


class SearchResponse(BaseModel):
    """Parsed Primo search response."""

    info: SearchInfo = SearchInfo()
    records: list[PrimoRecord] = []

    @classmethod
    def from_api_response(cls, data: dict) -> SearchResponse:
        """Parse the full /pnxs API response."""
        info_raw = data.get("info", {})
        info = SearchInfo(
            total=info_raw.get("total", 0),
            total_local=info_raw.get("totalResultsLocal", 0),
            total_pc=info_raw.get("totalResultsPC", 0),
            first=info_raw.get("first", 0),
            last=info_raw.get("last", 0),
        )
        records = [
            PrimoRecord.from_api_doc(doc)
            for doc in data.get("docs", [])
        ]
        return cls(info=info, records=records)
