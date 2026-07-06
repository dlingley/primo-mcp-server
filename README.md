# Primo MCP Server

MCP server for Purdue University library discovery via Ex
Libris Primo. It searches Purdue catalogue records, subscribed databases,
articles, books, videos, and database records through the Primo API.

This fork includes hardened scope handling, direct Primo record/search links,
and Unicode-safe handling for Chinese records.

## Features

- Search Primo catalogue, Primo Central Index, books/videos scopes, and subscribed databases
- Always return direct Primo search links and individual record links
- Get record details including title, authors, identifiers, subjects, description, source, availability, and record ID
- Preserve Chinese and other Unicode metadata in search results, details, citations, and exports
- Generate citations in APA 7th, Harvard, Chicago, IEEE, and Vancouver styles
- Export records to BibTeX, RIS, or UTF-8-sig CSV
- Reject invalid search scopes instead of silently falling back to Everything
- Append a "Result landscape" facet summary (resource types, top subjects, creators, journals, languages, availability, publication years) so zero-result and too-many-result searches can be refined from data instead of guesswork
- Act on that landscape with generic facet filters: `facet_filters={"topic": "Economics"}` narrows to a facet value, `facet_exclusions` removes one (any Primo facet, e.g. topic, lang, jtitle, tlevel, library)
- Compound boolean queries: multi-clause AND/OR/NOT with contains/exact/begins_with operators for known-item lookups (title AND creator), exact-title checks, and OR expansion
- Show physical shelf locations (library, location, call number, availability status) and direct full-text access links (proxied resource links, Alma link-resolver openurl) in search results and record details

## Quick Start for Purdue

Clone and install the fork:

```bash
git clone https://github.com/aarontaycheehsien/purduelibrary-mcp-server.git
cd purduelibrary-mcp-server
pip install -e .
```

Register it in Claude Code by adding this to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "primo": {
      "command": "python",
      "args": ["-m", "purduelibrary_mcp_server"]
    }
  }
}
```

Restart Claude Code. The tools will appear as `mcp__primo__primo_search`,
`mcp__primo__primo_get_record`, and related tool names.

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Tools

| Tool | Description |
|------|-------------|
| `primo_search` | Search Primo with field, scope, type, date, and peer-review filters |
| `primo_get_record` | Get full details for a record by Primo record ID |
| `primo_suggest` | Get autocomplete suggestions |
| `primo_cite` | Generate formatted citations |
| `primo_export` | Export records as BibTeX, RIS, or CSV |

## Scope Behaviour

Use these canonical scopes:

| Scope | Covers | Common aliases |
|-------|--------|----------------|
| `catalogue` | Local catalogue records, including books, databases, and videos | `catalog`, `local`, `myinstitution`, `my_institution` |
| `everything` | Local catalogue plus Primo Central Index articles and remote records | `all`, `combined`, `myinst_and_ci`, `pci` |
| `books_videos` | Institution books/videos tab where configured | `booksvideos`, `booksandvideos`, `books/videos`, `books & videos` |

Recommended caller policy:

- For books, databases, and videos, start with `scope="catalogue"`.
- For articles, start with `scope="everything"`.
- For dataset or data-source requests, start with `scope="catalogue"` and `resource_type="databases"` to find subscribed data platforms first. Expand to articles or books only after database results are weak, irrelevant, or empty, and say that the search was expanded beyond databases.
- For catalogue searches with no results, retry with `scope="everything"` only when the user did not ask for catalogue-only results.
- For any zero-result search, reason about why the query failed and try revised `primo_search` calls up to five total attempts. Good retries may broaden an over-specific phrase, use synonyms or related concepts, try singular/plural variants, switch fields, relax filters, widen scope when permitted, search directly for likely database names, or use OR queries for close alternatives.
- When summarising an iterative search, combine all relevant results found across attempts and report the attempted queries.
- For access or subscription checks, use Primo results as the evidence source rather than websites or LibGuides.

## Compound Queries

`primo_search` accepts an optional `clauses` list that compiles to Primo's
multi-clause boolean syntax and replaces the single `query`/`field` pair as
the retrieval query (`query` should still carry a short plain-text summary
for display). Each clause has a `value`,
optional `field` (`any`, `title`, `creator`, `sub`, `isbn`, `issn`,
`oclcnum`), optional `operator` (`contains`, `exact`, `begins_with`), and
optional `connector` (`AND`, `OR`, `NOT`) joining it to the next clause:

```json
{
  "query": "piketty capital",
  "clauses": [
    {"field": "title", "value": "capital", "connector": "AND"},
    {"field": "creator", "value": "piketty"}
  ]
}
```

Use compound queries for known-item lookups (title AND creator), exact-title
subscription checks, genuine OR expansion across synonyms, or NOT exclusion.
The result header links to the equivalent Primo advanced search.

## Purdue Configuration

Purdue is the default configuration for this fork. You can run without a `.env`
file for Purdue, or create one to make the settings explicit:

```env
PRIMO_BASE_URL=https://purdue.primo.exlibrisgroup.com/primaws/rest/pub
PRIMO_DISCOVERY_BASE_URL=https://purdue.primo.exlibrisgroup.com/discovery
PRIMO_VID=01PURDUE_PUWL:PURDUE
PRIMO_INSTITUTION_NAME=Purdue University

PRIMO_TAB_EVERYTHING=Everything
PRIMO_TAB_CATALOGUE=Catalogue
PRIMO_TAB_BOOKS_VIDEOS=booksandvideos

PRIMO_SCOPE_COMBINED=MyInst_and_CI
PRIMO_SCOPE_LOCAL=MyInstitution
PRIMO_SCOPE_BOOKS_VIDEOS=BooksVideos

PRIMO_LANGUAGE=en
PRIMO_REQUEST_TIMEOUT=30.0
PRIMO_MAX_RESULTS_PER_REQUEST=50
PRIMO_DEFAULT_RESULTS=10
```

## Configuration Reference

Defaults are set for Purdue. Other institutions can override these values with
environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PRIMO_BASE_URL` | `https://purdue.primo.exlibrisgroup.com/primaws/rest/pub` | Primo API base URL |
| `PRIMO_DISCOVERY_BASE_URL` | Derived from `PRIMO_BASE_URL` | Primo web app base URL for record and search links |
| `PRIMO_VID` | `01PURDUE_PUWL:PURDUE` | Primo view ID |
| `PRIMO_INSTITUTION_CODE` | Derived from `PRIMO_VID` | Institution code for the guest JWT endpoint |
| `PRIMO_INSTITUTION_NAME` | `Purdue University` | Display name |
| `PRIMO_TAB_EVERYTHING` | `Everything` | Primo tab for combined local and CDI searches |
| `PRIMO_TAB_CATALOGUE` | `Catalogue` | Primo tab for local catalogue searches |
| `PRIMO_TAB_BOOKS_VIDEOS` | `booksandvideos` | Primo tab for books/videos searches |
| `PRIMO_SCOPE_COMBINED` | `MyInst_and_CI` | Primo scope for combined local and CDI searches |
| `PRIMO_SCOPE_LOCAL` | `MyInstitution` | Primo scope for local catalogue searches |
| `PRIMO_SCOPE_BOOKS_VIDEOS` | `BooksVideos` | Primo scope for books/videos searches |
| `PRIMO_REQUEST_TIMEOUT` | `30.0` | HTTP timeout in seconds |
| `PRIMO_REQUEST_RETRY_ATTEMPTS` | `1` | Extra attempts after a transient Primo failure (timeout, connection error, HTTP 429/5xx); `0` disables retries |
| `PRIMO_REQUEST_RETRY_MAX_DELAY` | `5.0` | Cap in seconds on the retry backoff, including a server-sent `Retry-After` |
| `PRIMO_MAX_RESULTS_PER_REQUEST` | `50` | Maximum results per search request |
| `PRIMO_DEFAULT_RESULTS` | `10` | Default results per search |
| `PRIMO_LANGUAGE` | `en` | Primo language parameter |
| `PRIMO_INCLUDE_UNAVAILABLE` | `false` | Include CDI records without full text access in search results |
| `PRIMO_SEARCH_FACETS` | `true` | Fetch the facet summary after each search and append a "Result landscape" section (facets are only served for the Everything scope; other scopes omit the section) |

See `.env.example` for a commented template.

## Usage Examples

From a Claude Code conversation:

- "Search the catalogue for books on rural poverty in Indiana"
- "Search Everything for peer-reviewed articles on open access citation advantage"
- "Do we have access to JSTOR?"
- "search for databases with data on cost of living"
- "Get the full details for record alma991234567890"
- "Generate APA7 citations for these records"
- "Export these records as BibTeX"

## Licence

MIT
