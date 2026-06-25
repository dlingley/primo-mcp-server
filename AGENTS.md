# Primo MCP Server

Purdue-focused MCP server for searching Purdue University Libraries
Primo catalogue, articles, databases, books, videos, and records through the Ex
Libris Primo discovery API.

This is the canonical agent guidance file for this fork.

## Architecture

- **Framework:** FastMCP (mcp.server.fastmcp)
- **Transport:** stdio
- **HTTP client:** httpx (async, connection-pooled)
- **Config:** pydantic-settings with PRIMO_ env prefix

## Key Files

- `src/purduelibrary_mcp_server/server.py` -- MCP tool definitions and lifespan
- `src/purduelibrary_mcp_server/client.py` -- Primo API HTTP client
- `src/purduelibrary_mcp_server/models.py` -- Pydantic models for PNX response normalisation
- `src/purduelibrary_mcp_server/formatter.py` -- Compact text output for LLM context
- `src/purduelibrary_mcp_server/citations.py` -- Citation formatting (APA7, Harvard, Chicago, IEEE, Vancouver)
- `src/purduelibrary_mcp_server/exporters.py` -- BibTeX, RIS, CSV export

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Configuration

Defaults are Purdue (Purdue University). Other institutions can
override these values with environment variables, but public documentation and
agent behaviour should remain Purdue-first for this fork.

- PRIMO_BASE_URL -- Primo API base URL
- PRIMO_DISCOVERY_BASE_URL -- Primo web app base URL for search and record links
- PRIMO_VID -- View ID for the institution
- PRIMO_INSTITUTION_NAME -- Display name
- PRIMO_TAB_CATALOGUE / PRIMO_SCOPE_LOCAL -- Purdue catalogue search
- PRIMO_TAB_EVERYTHING / PRIMO_SCOPE_COMBINED -- Purdue catalogue plus CDI search
- PRIMO_TAB_BOOKS_VIDEOS / PRIMO_SCOPE_BOOKS_VIDEOS -- Purdue books/videos search

## Search Scope Policy

Use Primo as the evidence source for library holdings, subscriptions, and
access checks. Do not use websites, LibGuides, or general web pages as
evidence for those confirmation requests unless the user explicitly asks for
web confirmation.

When asked to search the catalogue, call `primo_search` with
`scope="catalogue"` first. If that returns no results and the user did not
ask for catalogue-only results, retry with `scope="everything"` and say that
the search was widened.

For books, databases, and videos, default to `scope="catalogue"`. For
articles, default to `scope="everything"`.

## Conventions

- Australian English (en-AU)
- UTF-8-sig for CSV exports
- No contractions in prose
- ASCII-only in generated content
