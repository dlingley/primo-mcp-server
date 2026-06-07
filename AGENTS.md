# Primo MCP Server

MCP server for searching university library catalogues via the Ex Libris Primo discovery API.

## Architecture

- **Framework:** FastMCP (mcp.server.fastmcp)
- **Transport:** stdio
- **HTTP client:** httpx (async, connection-pooled)
- **Config:** pydantic-settings with PRIMO_ env prefix

## Key Files

- `src/primo_mcp_server/server.py` -- MCP tool definitions and lifespan
- `src/primo_mcp_server/client.py` -- Primo API HTTP client
- `src/primo_mcp_server/models.py` -- Pydantic models for PNX response normalisation
- `src/primo_mcp_server/formatter.py` -- Compact text output for LLM context
- `src/primo_mcp_server/citations.py` -- Citation formatting (APA7, Harvard, Chicago, IEEE, Vancouver)
- `src/primo_mcp_server/exporters.py` -- BibTeX, RIS, CSV export

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Configuration

Defaults are UWA. Override via environment variables:
- PRIMO_BASE_URL -- Primo API base URL
- PRIMO_VID -- View ID for the institution
- PRIMO_INSTITUTION_NAME -- Display name

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
