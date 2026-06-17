"""Validation and normalisation for Primo query parameters."""

from __future__ import annotations

import re


_SCOPE_ALIASES = {
    "catalogue": "catalogue",
    "catalog": "catalogue",
    "local": "catalogue",
    "myinstitution": "catalogue",
    "my_institution": "catalogue",
    "everything": "everything",
    "all": "everything",
    "combined": "everything",
    "myinst_and_ci": "everything",
    "pci": "everything",
    "books_videos": "books_videos",
    "booksvideos": "books_videos",
    "booksandvideos": "books_videos",
    "books/videos": "books_videos",
    "books_&_videos": "books_videos",
    "books_and_videos": "books_videos",
}

_FIELD_ALIASES = {
    "any": "any",
    "title": "title",
    "creator": "creator",
    "author": "creator",
    "authors": "creator",
    "subject": "sub",
    "subjects": "sub",
    "sub": "sub",
    "isbn": "isbn",
    "issn": "issn",
    "oclc": "oclcnum",
    "oclcnum": "oclcnum",
}

_SORT_ALIASES = {
    "rank": "rank",
    "relevance": "rank",
    "date": "date",
    "newest": "date",
    "title": "title",
}

_RESOURCE_TYPE_ALIASES = {
    "article": "articles",
    "articles": "articles",
    "book": "books",
    "books": "books",
    "journal": "journals",
    "journals": "journals",
    "database": "databases",
    "databases": "databases",
    "video": "videos",
    "videos": "videos",
    "dissertation": "dissertations",
    "dissertations": "dissertations",
    "thesis": "dissertations",
    "conference_proceeding": "conference_proceedings",
    "conference_proceedings": "conference_proceedings",
    "conference proceeding": "conference_proceedings",
    "conference proceedings": "conference_proceedings",
}

_YEAR_RE = re.compile(r"^\d{4}$")


def _key(value: str | None) -> str:
    return (value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _valid_options(aliases: dict[str, str]) -> str:
    return ", ".join(sorted(set(aliases.values())))


def _normalise_alias(value: str, aliases: dict[str, str], label: str) -> str:
    key = _key(value)
    try:
        return aliases[key]
    except KeyError as e:
        raise ValueError(
            f'Invalid {label} "{value}". Use one of: {_valid_options(aliases)}.'
        ) from e


def normalise_scope(scope: str) -> str:
    """Resolve caller-friendly scope aliases to canonical scope names."""
    return _normalise_alias(scope, _SCOPE_ALIASES, "scope")


def normalise_search_field(field: str) -> str:
    """Resolve caller-friendly search field aliases to Primo field names."""
    return _normalise_alias(field, _FIELD_ALIASES, "search field")


def normalise_sort_by(sort_by: str) -> str:
    """Resolve caller-friendly sort aliases to Primo sort names."""
    return _normalise_alias(sort_by, _SORT_ALIASES, "sort_by")


def normalise_resource_type(resource_type: str | None) -> str | None:
    """Resolve caller-friendly resource type aliases to Primo facet values."""
    if resource_type is None:
        return None
    return _normalise_alias(resource_type, _RESOURCE_TYPE_ALIASES, "resource_type")


def normalise_year(value: str | None, label: str) -> str | None:
    """Validate and strip a four-digit year parameter."""
    if value is None:
        return None
    year = value.strip()
    if not _YEAR_RE.match(year):
        raise ValueError(f'Invalid {label} "{value}". Use YYYY format, e.g. "2020".')
    return year


def normalise_date_range(
    date_from: str | None,
    date_to: str | None,
) -> tuple[str | None, str | None]:
    """Validate year filters and return stripped values."""
    start = normalise_year(date_from, "date_from")
    end = normalise_year(date_to, "date_to")
    if end and not start:
        raise ValueError("date_to requires date_from.")
    if start and end and int(end) < int(start):
        raise ValueError("date_to must be greater than or equal to date_from.")
    return start, end


def date_range_facet_value(date_from: str | None, date_to: str | None) -> str | None:
    """Return Primo's documented creation-date range facet value."""
    start, end = normalise_date_range(date_from, date_to)
    if not start:
        return None
    return f"[{start} TO {end or start}]"
