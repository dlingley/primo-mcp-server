# Primo MCP Server

MCP server for Ex Libris Primo library discovery. It searches university
catalogues, subscribed databases, articles, books, videos, and database
records through the Primo API.

This fork includes hardened scope handling, direct Primo record/search links,
and Unicode-safe handling for Chinese records.

## Features

- Search Primo catalogue, Primo Central Index, books/videos scopes, and subscribed databases
- Return direct Primo links for searches and individual records
- Get record details including title, authors, identifiers, subjects, description, source, availability, and record ID
- Preserve Chinese and other Unicode metadata in search results, details, citations, and exports
- Generate citations in APA 7th, Harvard, Chicago, IEEE, and Vancouver styles
- Export records to BibTeX, RIS, or UTF-8-sig CSV
- Reject invalid search scopes instead of silently falling back to Everything

## Installation

```bash
git clone https://github.com/aarontaycheehsien/primo-mcp-server.git
cd primo-mcp-server
pip install -e .
```

For development and tests:

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Register in Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "primo": {
      "command": "python",
      "args": ["-m", "primo_mcp_server"]
    }
  }
}
```

Restart Claude Code. The tools will appear as `mcp__primo__primo_search`,
`mcp__primo__primo_get_record`, and related tool names.

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
- For catalogue searches with no results, retry with `scope="everything"` only when the user did not ask for catalogue-only results.
- For access or subscription checks, use Primo results as the evidence source rather than websites or LibGuides.

## SMU Configuration

Create a `.env` file with:

```env
PRIMO_BASE_URL=https://search.library.smu.edu.sg/primaws/rest/pub
PRIMO_DISCOVERY_BASE_URL=https://search.library.smu.edu.sg/discovery
PRIMO_VID=65SMU_INST:SMU_NUI
PRIMO_INSTITUTION_NAME=SMU

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

Defaults are set for UWA. Override via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PRIMO_BASE_URL` | `https://onesearch.library.uwa.edu.au/primaws/rest/pub` | Primo API base URL |
| `PRIMO_DISCOVERY_BASE_URL` | Derived from `PRIMO_BASE_URL` | Primo web app base URL for record and search links |
| `PRIMO_VID` | `61UWA_INST:NDE_UWA` | Primo view ID |
| `PRIMO_INSTITUTION_NAME` | `UWA` | Display name |
| `PRIMO_TAB_EVERYTHING` | `Everything` | Primo tab for combined local and CDI searches |
| `PRIMO_TAB_CATALOGUE` | `Catalogue` | Primo tab for local catalogue searches |
| `PRIMO_TAB_BOOKS_VIDEOS` | `booksandvideos` | Primo tab for books/videos searches |
| `PRIMO_SCOPE_COMBINED` | `MyInst_and_CI` | Primo scope for combined local and CDI searches |
| `PRIMO_SCOPE_LOCAL` | `MyInstitution` | Primo scope for local catalogue searches |
| `PRIMO_SCOPE_BOOKS_VIDEOS` | `BooksVideos` | Primo scope for books/videos searches |
| `PRIMO_REQUEST_TIMEOUT` | `30.0` | HTTP timeout in seconds |
| `PRIMO_MAX_RESULTS_PER_REQUEST` | `50` | Maximum results per search request |
| `PRIMO_DEFAULT_RESULTS` | `10` | Default results per search |
| `PRIMO_LANGUAGE` | `en` | Primo language parameter |

See `.env.example` for a commented template.

## Usage Examples

From a Claude Code conversation:

- "Search the catalogue for books on poverty in Singapore"
- "Search Everything for peer-reviewed articles on open access citation advantage"
- "Do we have access to JSTOR?"
- "Get the full details for record alma991234567890"
- "Generate APA7 citations for these records"
- "Export these records as BibTeX"

## Licence

MIT
