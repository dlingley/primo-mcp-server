"""Format Primo records into compact, LLM-friendly text output."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlencode

from primo_mcp_server.models import PrimoRecord, SearchResponse

if TYPE_CHECKING:
    from primo_mcp_server.config import PrimoConfig


_PRIMO_API_SUFFIX = "/primaws/rest/pub"
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
    "books & videos": "books_videos",
}


def _format_authors(creators: list[str], max_authors: int = 3) -> str:
    """Format an author list, truncating with 'et al.' if needed."""
    if not creators:
        return "Unknown author"
    if len(creators) <= max_authors:
        return "; ".join(creators)
    return "; ".join(creators[:max_authors]) + " et al."


def _format_identifiers(record: PrimoRecord) -> str:
    """Format the most useful identifier for a record."""
    parts = []
    if record.doi:
        parts.append(f"DOI: {record.doi}")
    if record.isbn:
        parts.append(f"ISBN: {record.isbn[0]}")
    if record.issn:
        parts.append(f"ISSN: {record.issn[0]}")
    return " | ".join(parts) if parts else ""


def _format_availability(record: PrimoRecord) -> str:
    """Format availability information."""
    parts = []
    if record.fulltext_available:
        parts.append("Full text available")
    if record.delivery_category:
        parts.append(record.delivery_category)
    return " | ".join(parts) if parts else "Check availability in OneSearch"


def _derive_discovery_base_url(base_url: str) -> str:
    """Derive the Primo discovery app root from a Primo API base URL."""
    trimmed = base_url.rstrip("/")
    if trimmed.lower().endswith(_PRIMO_API_SUFFIX):
        return trimmed[: -len(_PRIMO_API_SUFFIX)]
    return trimmed


def _discovery_app_base_url(config: PrimoConfig) -> str:
    """Return the discovery app base URL, ending in /discovery."""
    base = (config.discovery_base_url or _derive_discovery_base_url(config.base_url)).rstrip("/")
    if not base:
        return ""
    if base.lower().endswith("/discovery"):
        return base
    return f"{base}/discovery"


def _search_scope_params(config: PrimoConfig, scope: str) -> tuple[str, str] | None:
    """Return Primo UI tab and search_scope values for a caller scope."""
    key = scope.strip().lower().replace("-", "_") if scope else ""
    canonical_scope = _SCOPE_ALIASES.get(key)
    if canonical_scope == "catalogue":
        return config.tab_catalogue, config.scope_local
    if canonical_scope == "everything":
        return config.tab_everything, config.scope_combined
    if canonical_scope == "books_videos":
        return config.tab_books_videos, config.scope_books_videos
    return None


def _record_context(record: PrimoRecord) -> str:
    """Return the Primo full-display context for a local or remote record."""
    if record.context.strip().upper() == "L":
        return "L"
    if record.record_id.lower().startswith("alma"):
        return "L"

    source_values = (record.source_id, record.source_system, record.source_label)
    if any("alma" in value.lower() for value in source_values if value):
        return "L"
    return "PC"


def build_record_url(record: PrimoRecord, config: PrimoConfig | None = None) -> str | None:
    """Build a direct Primo full-display URL for a record."""
    if config is None or not record.record_id or not config.vid:
        return None

    app_base = _discovery_app_base_url(config)
    if not app_base:
        return None

    params = urlencode(
        {
            "docid": record.record_id,
            "context": _record_context(record),
            "vid": config.vid,
            "lang": config.language,
        }
    )
    return f"{app_base}/fulldisplay?{params}"


def build_search_url(
    query: str,
    config: PrimoConfig | None = None,
    *,
    field: str = "any",
    scope: str = "everything",
    sort_by: str = "rank",
    offset: int = 0,
    resource_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    peer_reviewed: bool | None = None,
) -> str | None:
    """Build a direct Primo UI search URL for the search response."""
    if config is None or not query or not config.vid:
        return None

    app_base = _discovery_app_base_url(config)
    scope_params = _search_scope_params(config, scope)
    if not app_base or scope_params is None:
        return None

    tab, search_scope = scope_params
    params: list[tuple[str, str]] = [
        ("query", f"{field},contains,{query}"),
        ("tab", tab),
        ("search_scope", search_scope),
        ("vid", config.vid),
        ("lang", config.language),
        ("offset", str(max(0, offset))),
    ]
    if sort_by:
        params.append(("sortby", sort_by))
    if resource_type:
        params.append(("facet", f"rtype,include,{resource_type}"))
    if date_from and date_to:
        for year in range(int(date_from), int(date_to) + 1):
            params.append(("facet", f"creationdate,include,{year}"))
    elif date_from:
        params.append(("facet", f"creationdate,include,{date_from}"))
    if peer_reviewed:
        params.append(("facet", "tlevel,include,peer_reviewed"))

    return f"{app_base}/search?{urlencode(params)}"


def _markdown_link_text(text: str) -> str:
    """Escape Markdown link text while preserving Unicode metadata."""
    return text.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def _format_title(record: PrimoRecord, config: PrimoConfig | None = None) -> str:
    """Format a record title as a link when a Primo URL can be built."""
    url = build_record_url(record, config)
    if not url:
        return record.title
    return f"[{_markdown_link_text(record.title)}]({url})"


def format_search_results(
    response: SearchResponse,
    query: str,
    offset: int = 0,
    config: PrimoConfig | None = None,
    field: str = "any",
    scope: str = "everything",
    sort_by: str = "rank",
    resource_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    peer_reviewed: bool | None = None,
) -> str:
    """Format search results as a compact numbered list.

    Each result is 3-5 lines: title, authors, metadata, identifiers, availability.
    """
    search_url = build_search_url(
        query,
        config,
        field=field,
        scope=scope,
        sort_by=sort_by,
        offset=offset,
        resource_type=resource_type,
        date_from=date_from,
        date_to=date_to,
        peer_reviewed=peer_reviewed,
    )
    search_link = (
        f"Search in Primo: [Open search]({search_url})\n\n"
        if search_url else ""
    )

    if not response.records:
        return (
            f'No results found for "{query}".\n\n'
            f"{search_link}"
            "Suggestions:\n"
            "- Broaden your search terms\n"
            "- Check spelling\n"
            "- Try a different search field (title, creator, subject)\n"
            "- Remove filters (resource type, date range)"
        )

    total = f"{response.info.total:,}"
    showing_start = offset + 1
    showing_end = offset + len(response.records)

    lines = [
        f'Found {total} results for "{query}" (showing {showing_start}-{showing_end})',
        "",
    ]
    if search_url:
        lines.extend([f"Search in Primo: [Open search]({search_url})", ""])

    for i, record in enumerate(response.records, start=showing_start):
        # Line 1: number, title, year, type
        type_badge = record.resource_type.replace("_", " ").title() if record.resource_type else "Unknown"
        year = record.year or "n.d."

        lines.append(f"[{i}] {_format_title(record, config)}")
        lines.append(f"    {_format_authors(record.display_authors)} | {year} | {type_badge}")

        # Line 3: journal/source + identifiers
        source_parts = []
        if record.journal_title:
            journal_info = record.journal_title
            if record.volume:
                journal_info += f", {record.volume}"
            if record.issue:
                journal_info += f"({record.issue})"
            if record.start_page:
                journal_info += f", pp. {record.start_page}"
                if record.end_page:
                    journal_info += f"-{record.end_page}"
            source_parts.append(journal_info)
        elif record.publisher:
            source_parts.append(record.publisher)

        ident = _format_identifiers(record)
        if ident:
            source_parts.append(ident)
        if source_parts:
            lines.append(f"    {' | '.join(source_parts)}")

        # Line 4: availability + peer review + record ID
        status_parts = []
        if record.peer_reviewed:
            status_parts.append("Peer-reviewed")
        status_parts.append(_format_availability(record))
        lines.append(f"    {' | '.join(status_parts)}")
        lines.append(f"    Record ID: {record.record_id}")
        lines.append("")

    return "\n".join(lines).rstrip()


def format_record_detail(record: PrimoRecord, config: PrimoConfig | None = None) -> str:
    """Format a single record with full details."""
    lines = []

    lines.append(f"Title: {_format_title(record, config)}")
    lines.append(f"Author(s): {_format_authors(record.display_authors, max_authors=10)}")

    # Show contributors only when they add names beyond those already listed
    # as authors (avoids duplication when contributors are the author fallback).
    extra_contributors = [c for c in record.contributors if c not in record.display_authors]
    if extra_contributors:
        lines.append(f"Contributor(s): {'; '.join(extra_contributors)}")

    year = record.year or "n.d."
    lines.append(f"Year: {year}")
    lines.append(f"Type: {record.resource_type.replace('_', ' ').title() if record.resource_type else 'Unknown'}")

    if record.publisher:
        lines.append(f"Publisher: {record.publisher}")

    if record.journal_title:
        journal = record.journal_title
        if record.volume:
            journal += f", vol. {record.volume}"
        if record.issue:
            journal += f", no. {record.issue}"
        if record.start_page:
            journal += f", pp. {record.start_page}"
            if record.end_page:
                journal += f"-{record.end_page}"
        lines.append(f"Journal: {journal}")

    if record.language:
        lines.append(f"Language: {record.language}")

    # Identifiers
    if record.doi:
        lines.append(f"DOI: {record.doi}")
    if record.isbn:
        lines.append(f"ISBN: {', '.join(record.isbn)}")
    if record.issn:
        lines.append(f"ISSN: {', '.join(record.issn)}")

    if record.subjects:
        lines.append(f"Subjects: {'; '.join(record.subjects)}")
    if record.keywords:
        lines.append(f"Keywords: {'; '.join(record.keywords)}")

    lines.append(f"Peer-reviewed: {'Yes' if record.peer_reviewed else 'No'}")

    if record.description:
        # Truncate long descriptions
        desc = record.description
        if len(desc) > 500:
            desc = desc[:497] + "..."
        lines.append(f"\nDescription:\n{desc}")

    # Availability
    lines.append(f"\nAvailability: {_format_availability(record)}")
    if record.source_label:
        lines.append(f"Source: {record.source_label}")

    lines.append(f"Record ID: {record.record_id}")

    return "\n".join(lines)


def format_suggestions(suggestions: list[str], query: str) -> str:
    """Format autocomplete suggestions."""
    if not suggestions:
        return f'No suggestions found for "{query}".'

    lines = [f'Suggestions for "{query}":', ""]
    for s in suggestions:
        lines.append(f"  - {s}")
    return "\n".join(lines)
