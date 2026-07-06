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
- `src/purduelibrary_mcp_server/policy.py` -- Single source of truth for the caller-facing scope and zero-result policy prose (server instructions, primo_search description, and zero-result output are all composed from it)
- `src/purduelibrary_mcp_server/client.py` -- Primo API HTTP client
- `src/purduelibrary_mcp_server/config.py` -- pydantic-settings configuration (PRIMO_ env prefix)
- `src/purduelibrary_mcp_server/query.py` -- scope, field, sort, and resource type alias normalisation
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

This section mirrors `src/purduelibrary_mcp_server/policy.py`, which is the single
source of truth the server actually serves to callers. When changing the
policy, edit `policy.py` first and keep this section and README.md in step.

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

For dataset or data-source requests, start with `scope="catalogue"` and
`resource_type="databases"` to find subscribed data platforms first. Expand
to articles or books only after database results are weak, irrelevant, or
empty, and say that the search was expanded beyond databases.

For any zero-result search, reason about why the query failed and call
`primo_search` again with revised queries up to five total attempts. Good
retries may broaden an over-specific phrase, use synonyms or related
concepts, try singular/plural variants, switch fields, relax filters, or
widen scope when permitted. Retries may also search directly for likely
database names or use OR queries for close alternatives. When summarising,
combine all relevant results found across attempts and report the attempted
queries.


## Librarian Recommendation Policy

Recommendations are validated against the configured JSON profile
directory. Only configured librarian names may be returned; never invent
or substitute names. `primo_recommend_librarians` is the explicit tool;
`primo_search` appends inline recommendations by default (suppress with
`recommend_librarians=false`); `primo_list_librarians` returns the complete
configured directory when no recommendation clears the threshold or when
the user asks who the librarians are. Deterministic keyword matching runs
first, with an optional embedding fallback when keyword matches are weak
or absent. Identifier-shaped queries (DOI, ISBN, ISSN, record IDs) skip
recommendations entirely. Recommendation counts are capped at 3.

When tuning matching weights or thresholds, run the golden-query benchmark
before and after and report the delta:

```bash
python -m purduelibrary_mcp_server.evaluate_recommendations librarian-eval.json --keyword-only
```

## Conventions

- Australian English (en-AU)
- UTF-8-sig for CSV exports
- No contractions in prose
- ASCII-only in generated content
