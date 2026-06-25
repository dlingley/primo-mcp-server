"""FastMCP server exposing Primo library search tools."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from mcp.server.fastmcp import Context, FastMCP

from purduelibrary_mcp_server.client import PrimoAPIError, PrimoClient
from purduelibrary_mcp_server.config import PrimoConfig, SpringshareConfig
from purduelibrary_mcp_server.formatter import (
    format_record_detail,
    format_search_results,
    format_suggestions,
)
from purduelibrary_mcp_server.springshare import SpringshareAPIError, SpringshareClient


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Create shared httpx clients for the server lifetime."""
    config = PrimoConfig()
    ss_config = SpringshareConfig()
    async with httpx.AsyncClient(
        base_url=config.base_url,
        timeout=config.request_timeout,
        headers={"User-Agent": config.user_agent},
    ) as http_client, httpx.AsyncClient(
        timeout=ss_config.request_timeout,
        headers={"User-Agent": ss_config.user_agent},
    ) as ss_http_client:
        client = PrimoClient(http_client, config)
        ss_client = SpringshareClient(ss_http_client, ss_config)
        yield {
            "client": client,
            "config": config,
            "ss_client": ss_client,
            "ss_config": ss_config,
        }


mcp = FastMCP(
    "primo",
    instructions=(
        "Search Purdue University Libraries catalogue records, "
        "articles, databases, books, videos, and holdings via the Ex Libris "
        "Primo discovery API. "
        "Scope selection policy: when asked to search the catalogue, call "
        "primo_search with scope='catalogue' first; if that returns no "
        "results and the user did not ask for catalogue-only results, retry "
        "with scope='everything' and say that you widened the search. "
        "For books, databases, and videos, default to scope='catalogue'. "
        "For articles, default to scope='everything'. For confirmation "
        "requests about whether the library has, owns, subscribes to, or "
        "provides access to a title, use Primo as the evidence source and "
        "do not use websites, LibGuides, or general web pages unless the "
        "user explicitly asks for web confirmation. "
        "Use primo_search for queries, primo_get_record for full details, "
        "primo_suggest for autocomplete, primo_cite for citations, "
        "and primo_export for BibTeX/RIS/CSV export."
    ),
    lifespan=app_lifespan,
)


def _get_client(ctx: Context) -> PrimoClient:
    """Extract the PrimoClient from the lifespan context."""
    return ctx.request_context.lifespan_context["client"]


def _get_config(ctx: Context) -> PrimoConfig:
    """Extract the PrimoConfig from the lifespan context."""
    return ctx.request_context.lifespan_context["config"]


def _get_ss_client(ctx: Context) -> SpringshareClient:
    """Extract the SpringshareClient from the lifespan context."""
    return ctx.request_context.lifespan_context["ss_client"]


def _get_ss_config(ctx: Context) -> SpringshareConfig:
    """Extract the SpringshareConfig from the lifespan context."""
    return ctx.request_context.lifespan_context["ss_config"]


# ---------------------------------------------------------------------------
# Tool 1: primo_search
# ---------------------------------------------------------------------------

@mcp.tool()
async def primo_search(
    ctx: Context,
    query: str,
    field: str = "any",
    scope: str = "everything",
    sort_by: str = "rank",
    limit: int = 10,
    offset: int = 0,
    resource_type: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    peer_reviewed: bool | None = None,
    include_unavailable: bool | None = None,
    online: bool | None = None,
) -> str:
    """Search Purdue University Libraries via Primo.

    Scope selection policy for callers:
    - When asked to search the catalogue, use scope="catalogue" first. If
      that returns no results and the user did not ask for catalogue-only
      results, retry with scope="everything" and say that the search was
      widened.
    - For books, databases, and videos, default to scope="catalogue".
    - For articles, default to scope="everything".
    - For confirmation requests about whether the library has, owns,
      subscribes to, or provides access to a title, use Primo as the
      evidence source. Do not rely on websites, LibGuides, or general web
      pages unless the user explicitly asks for web confirmation.

    Args:
        query: Search terms (e.g. "machine learning entrepreneurship").
        field: Search field -- "any" (default), "title", "creator", "sub" (subject), "isbn", "oclcnum".
        scope: "everything" for local catalogue + subscribed databases, "catalogue" for local only, "books_videos" for the books/videos scope.
        sort_by: "rank" (relevance, default), "date" (newest first), "title" (alphabetical).
        limit: Number of results to return (1-50, default 10).
        offset: Pagination offset (default 0). Use to get the next page of results.
        resource_type: Filter by type -- "books", "articles", "journals", "databases", "videos", "dissertations", "conference_proceedings".
        date_from: Start year filter (YYYY format, e.g. "2020").
        date_to: End year filter (YYYY format, e.g. "2025").
        peer_reviewed: Set to true to show only peer-reviewed items.
        include_unavailable: Set to true to also include article-index (CDI)
            records the library has NO full text access to (Primo's
            "expanded" search). Default (false) restricts results to
            accessible material, which is what holdings and access
            confirmation requires. Only set true when the user explicitly
            wants to discover material beyond the library's collection,
            e.g. for interlibrary loan or comprehensive literature mapping.
        online: Set to true to show only online resources.

    Returns:
        Formatted search results with title, authors, year, identifiers, and availability.
    """
    try:
        client = _get_client(ctx)
        config = _get_config(ctx)
        response = await client.search(
            query=query,
            field=field,
            scope=scope,
            sort_by=sort_by,
            limit=limit,
            offset=offset,
            resource_type=resource_type,
            date_from=date_from,
            date_to=date_to,
            peer_reviewed=peer_reviewed,
            include_unavailable=include_unavailable,
            online=online,
        )
        return format_search_results(
            response,
            query,
            offset,
            config=config,
            field=field,
            scope=scope,
            sort_by=sort_by,
            resource_type=resource_type,
            date_from=date_from,
            date_to=date_to,
            peer_reviewed=peer_reviewed,
            include_unavailable=include_unavailable,
            online=online,
        )
    except PrimoAPIError as e:
        return f"Error searching Primo: {e}"
    except Exception as e:
        return f"Unexpected error: {e}"


# ---------------------------------------------------------------------------
# Tool 2: primo_get_record
# ---------------------------------------------------------------------------

@mcp.tool()
async def primo_get_record(ctx: Context, record_id: str) -> str:
    """Get full details for a single library record.

    Use the record ID from primo_search results to fetch complete metadata
    including abstract, all authors, subjects, identifiers, and availability.

    Args:
        record_id: The Primo record ID (from search results, e.g. "alma991234567890" or "cdi_crossref_primary_10_1234").

    Returns:
        Full record details including title, authors, abstract, identifiers, and availability.
    """
    try:
        client = _get_client(ctx)
        config = _get_config(ctx)
        record = await client.get_record(record_id)
        if record is None:
            return (
                f'Record "{record_id}" not found. '
                "It may have been removed, or the ID may be incorrect. "
                "Try searching again with primo_search."
            )
        return format_record_detail(record, config=config)
    except PrimoAPIError as e:
        return f"Error fetching record: {e}"
    except Exception as e:
        return f"Unexpected error: {e}"


# ---------------------------------------------------------------------------
# Tool 3: primo_suggest
# ---------------------------------------------------------------------------

@mcp.tool()
async def primo_suggest(ctx: Context, query: str) -> str:
    """Get autocomplete suggestions for a search term.

    Useful for refining searches, checking subject headings, or exploring
    related terms before running a full search.

    Args:
        query: Partial search term (e.g. "entrepre" or "machine lear").

    Returns:
        List of suggested search terms.
    """
    try:
        client = _get_client(ctx)
        suggestions = await client.suggest(query)
        return format_suggestions(suggestions, query)
    except PrimoAPIError as e:
        return f"Error getting suggestions: {e}"
    except Exception as e:
        return f"Unexpected error: {e}"


# ---------------------------------------------------------------------------
# Tool 4: primo_cite
# ---------------------------------------------------------------------------

@mcp.tool()
async def primo_cite(
    ctx: Context,
    record_ids: list[str],
    style: str = "apa7",
) -> str:
    """Generate formatted citations for library records.

    Args:
        record_ids: List of Primo record IDs to cite.
        style: Citation style -- "apa7" (default), "harvard", "chicago", "ieee", "vancouver".

    Returns:
        Formatted citations. Note: always verify generated citations before submission.
    """
    try:
        from purduelibrary_mcp_server.citations import format_citation

        valid_styles = {"apa7", "harvard", "chicago", "ieee", "vancouver"}
        style = style.strip().lower()
        if style not in valid_styles:
            return f'Invalid citation style "{style}". Use one of: {", ".join(sorted(valid_styles))}'

        client = _get_client(ctx)
        records = await client.get_records(record_ids)

        if not records:
            return "No records found for the provided IDs."

        citations = []
        for record in records:
            citations.append(format_citation(record, style))

        result = "\n\n".join(citations)
        result += "\n\n-- Note: verify citations before submission. Automated formatting may not cover all edge cases."
        return result
    except PrimoAPIError as e:
        return f"Error fetching records for citation: {e}"
    except Exception as e:
        return f"Unexpected error: {e}"


# ---------------------------------------------------------------------------
# Tool 5: primo_export
# ---------------------------------------------------------------------------

@mcp.tool()
async def primo_export(
    ctx: Context,
    record_ids: list[str],
    format: str = "bibtex",
) -> str:
    """Export library records to reference manager formats.

    Args:
        record_ids: List of Primo record IDs to export.
        format: Export format -- "bibtex" (default), "ris", "csv".

    Returns:
        Formatted export data ready for import into reference managers (Zotero, Mendeley, EndNote).
    """
    try:
        from purduelibrary_mcp_server.exporters import export_bibtex, export_csv, export_ris

        valid_formats = {"bibtex", "ris", "csv"}
        format = format.strip().lower()
        if format not in valid_formats:
            return f'Invalid format "{format}". Use one of: {", ".join(sorted(valid_formats))}'

        client = _get_client(ctx)
        records = await client.get_records(record_ids)

        if not records:
            return "No records found for the provided IDs."

        if format == "bibtex":
            return export_bibtex(records)
        elif format == "ris":
            return export_ris(records)
        else:
            return export_csv(records)
    except PrimoAPIError as e:
        return f"Error fetching records for export: {e}"
    except Exception as e:
        return f"Unexpected error: {e}"


# ---------------------------------------------------------------------------
# Tool 6: springshare_search_databases
# ---------------------------------------------------------------------------

@mcp.tool()
async def springshare_search_databases(ctx: Context, query: str) -> str:
    """Search curated Purdue University A-Z databases via LibGuides v1.2 API.

    Use this tool to find specific curated databases subscribed to by Purdue
    Libraries (e.g. "JSTOR", "Business Source Complete", "LISTA").

    Args:
        query: Search term for databases (e.g. "statistics", "business").

    Returns:
        Formatted list of matching databases with descriptions and links.
    """
    try:
        client = _get_ss_client(ctx)
        matches = await client.search_databases(query)
        if not matches:
            return f'No databases found matching "{query}" in the curated A-Z list.'

        lines = [f'Found {len(matches)} curated databases for "{query}":', ""]
        for db in matches:
            name = db.get("name", "")
            url = db.get("url", "")
            description = db.get("description", "")
            vendor = db.get("az_vendor_name", "")
            
            # Format title as link
            title_line = f"### [{name}]({url})" if url else f"### {name}"
            if vendor:
                title_line += f" (Provider: {vendor})"
            lines.append(title_line)
            
            if description:
                lines.append(description)
                
            # Subjects
            subjects = db.get("subjects", []) or []
            subject_names = [sub.get("name", "") for sub in subjects if sub]
            if subject_names:
                lines.append(f"*Subjects: {'; '.join(subject_names)}*")
            lines.append("") # Empty separator
            
        return "\n".join(lines).strip()
    except SpringshareAPIError as e:
        return f"Error searching Springshare: {e}"
    except Exception as e:
        return f"Unexpected error: {e}"
