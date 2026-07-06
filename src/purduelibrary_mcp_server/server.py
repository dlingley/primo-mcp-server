"""FastMCP server exposing Primo library search tools."""

from __future__ import annotations

import functools
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from mcp.server.fastmcp import Context, FastMCP

from purduelibrary_mcp_server.citations import format_citation
from purduelibrary_mcp_server.client import PrimoAPIError, PrimoClient
from purduelibrary_mcp_server.config import PrimoConfig, SpringshareConfig
from purduelibrary_mcp_server.exporters import export_bibtex, export_csv, export_ris
from purduelibrary_mcp_server.formatter import (
    format_record_detail,
    format_search_results,
    format_suggestions,
)
from purduelibrary_mcp_server.policy import PRIMO_SEARCH_DESCRIPTION, SERVER_INSTRUCTIONS
from purduelibrary_mcp_server.query import QueryClause
from purduelibrary_mcp_server.springshare import (
    SpringshareAPIError,
    SpringshareClient,
    strip_html,
)

logger = logging.getLogger(__name__)


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
    instructions=SERVER_INSTRUCTIONS,
    lifespan=app_lifespan,
)


def _tool_error_boundary(action: str):
    """Uniform error boundary for MCP tools.

    Primo and Springshare API failures return their caller-facing message
    ("Error {action}: ..."); anything else is a bug, so the traceback is
    logged before the short message goes back to the caller -- without the
    log, unexpected errors were invisible one-liners.
    """

    def decorate(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except (PrimoAPIError, SpringshareAPIError) as e:
                return f"Error {action}: {e}"
            except Exception as e:
                logger.exception("Unexpected error in %s", func.__name__)
                return f"Unexpected error: {e}"

        return wrapper

    return decorate


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

@mcp.tool(description=PRIMO_SEARCH_DESCRIPTION)
@_tool_error_boundary("searching Primo")
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
    clauses: list[QueryClause] | None = None,
    facet_filters: dict[str, str] | None = None,
    facet_exclusions: dict[str, str] | None = None,
) -> str:
    """Search Purdue University Libraries via Primo.

    The caller-facing scope and zero-result retry policy plus the full
    argument reference live in policy.PRIMO_SEARCH_DESCRIPTION, which is
    served as this tool's description.
    """
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
        clauses=clauses,
        facet_filters=facet_filters,
        facet_exclusions=facet_exclusions,
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
        clauses=clauses,
    )


# ---------------------------------------------------------------------------
# Tool 2: primo_get_record
# ---------------------------------------------------------------------------

@mcp.tool()
@_tool_error_boundary("fetching record")
async def primo_get_record(ctx: Context, record_id: str) -> str:
    """Get full details for a single library record.

    Use the record ID from primo_search results to fetch complete metadata
    including abstract, all authors, subjects, identifiers, and availability.

    Args:
        record_id: The Primo record ID (from search results, e.g. "alma991234567890" or "cdi_crossref_primary_10_1234").

    Returns:
        Full record details including title, authors, abstract, identifiers, and availability.
    """
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


# ---------------------------------------------------------------------------
# Tool 3: primo_suggest
# ---------------------------------------------------------------------------

@mcp.tool()
@_tool_error_boundary("getting suggestions")
async def primo_suggest(ctx: Context, query: str) -> str:
    """Get autocomplete suggestions for a search term.

    Useful for refining searches, checking subject headings, or exploring
    related terms before running a full search.

    Args:
        query: Partial search term (e.g. "entrepre" or "machine lear").

    Returns:
        List of suggested search terms.
    """
    client = _get_client(ctx)
    suggestions = await client.suggest(query)
    return format_suggestions(suggestions, query)


# ---------------------------------------------------------------------------
# Tool 4: primo_cite
# ---------------------------------------------------------------------------

@mcp.tool()
@_tool_error_boundary("fetching records for citation")
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


# ---------------------------------------------------------------------------
# Tool 5: primo_export
# ---------------------------------------------------------------------------

@mcp.tool()
@_tool_error_boundary("fetching records for export")
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


# ---------------------------------------------------------------------------
# Tool 6: springshare_search_databases
# ---------------------------------------------------------------------------

@mcp.tool()
@_tool_error_boundary("searching Springshare")
async def springshare_search_databases(ctx: Context, query: str) -> str:
    """Search curated Purdue University A-Z databases via LibGuides v1.2 API.

    Use this tool to find specific curated databases subscribed to by Purdue
    Libraries (e.g. "JSTOR", "Business Source Complete", "LISTA").

    Args:
        query: Search term for databases (e.g. "statistics", "business").

    Returns:
        Formatted list of matching databases with descriptions and links.
    """
    client = _get_ss_client(ctx)
    ss_config = _get_ss_config(ctx)
    matches = await client.search_databases(query)
    if not matches:
        return f'No databases found matching "{query}" in the curated A-Z list.'

    total = len(matches)
    shown = matches[: max(1, ss_config.max_search_results)]
    if len(shown) < total:
        header = (
            f'Found {total} curated databases for "{query}" '
            f"(showing the top {len(shown)}; refine the query for more "
            "specific matches):"
        )
    else:
        header = f'Found {total} curated databases for "{query}":'
    lines = [header, ""]
    for db in shown:
        name = db.get("name", "")
        url = db.get("url", "")
        description = strip_html(db.get("description", ""))
        vendor = db.get("az_vendor_name", "")
        db_id = db.get("id")

        permalink = f"https://guides.lib.purdue.edu/az/databases?a={db_id}" if db_id else None

        title_line = f"### {name}"
        if vendor:
            title_line += f" (Provider: {vendor})"
        lines.append(title_line)

        links = []
        if url:
            links.append(f"[Direct Link]({url})")
        if permalink:
            links.append(f"[LibGuides Permalink]({permalink})")
        if links:
            lines.append(f"**Links**: {' | '.join(links)}")

        if description:
            lines.append(description)

        # Subjects
        subjects = db.get("subjects", []) or []
        subject_names = [sub.get("name", "") for sub in subjects if sub]
        if subject_names:
            lines.append(f"*Subjects: {'; '.join(subject_names)}*")
        lines.append("")  # Empty separator

    return "\n".join(lines).strip()
