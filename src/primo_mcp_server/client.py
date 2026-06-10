"""Async HTTP client for the Primo REST API."""

from __future__ import annotations

from typing import Any

import httpx

from primo_mcp_server.config import PrimoConfig
from primo_mcp_server.models import PrimoRecord, SearchResponse


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


def _normalise_scope(scope: str) -> str:
    """Resolve caller-friendly scope aliases to canonical scope names."""
    key = scope.strip().lower().replace("-", "_") if scope else ""
    try:
        return _SCOPE_ALIASES[key]
    except KeyError as e:
        valid = ", ".join(sorted(set(_SCOPE_ALIASES.values())))
        raise PrimoAPIError(
            f'Invalid scope "{scope}". Use one of: {valid}.',
            status_code=400,
        ) from e


def _normalise_alma_id(record_id: str) -> str:
    """Strip the Alma prefix for MMS-ID catalogue lookups and matching."""
    rid = record_id.strip()
    return rid[4:] if rid.lower().startswith("alma") else rid


def _date_range_facet_value(date_from: str | None, date_to: str | None) -> str | None:
    """Return Primo's documented creation-date range facet value."""
    if not date_from:
        return None
    return f"[{date_from} TO {date_to or date_from}]"


class PrimoAPIError(Exception):
    """Raised when the Primo API returns an error."""

    def __init__(self, message: str, status_code: int | None = None):
        self.status_code = status_code
        super().__init__(message)


class PrimoClient:
    """Async client for the Ex Libris Primo public API."""

    def __init__(self, http_client: httpx.AsyncClient, config: PrimoConfig):
        self._http = http_client
        self._config = config

    async def search(
        self,
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
    ) -> SearchResponse:
        """Search the Primo catalogue.

        Args:
            query: Search terms.
            field: Search field (any, title, creator, sub, isbn, oclcnum).
            scope: "everything" for local + PCI, "catalogue" for local only,
                "books_videos" for the institution's books/videos scope.
            sort_by: rank, date, or title.
            limit: Number of results (capped at max_results_per_request).
            offset: Pagination offset.
            resource_type: Filter by type (books, articles, journals, etc.).
            date_from: Start year (YYYY).
            date_to: End year (YYYY).
            peer_reviewed: Filter to peer-reviewed items only.

        Returns:
            SearchResponse with parsed records and pagination info.
        """
        cfg = self._config
        limit = min(max(1, limit), cfg.max_results_per_request)
        offset = max(0, offset)

        canonical_scope = _normalise_scope(scope)

        # Resolve scope to tab + scope params
        if canonical_scope == "catalogue":
            tab = cfg.tab_catalogue
            scope_param = cfg.scope_local
        elif canonical_scope == "everything":
            tab = cfg.tab_everything
            scope_param = cfg.scope_combined
        else:
            tab = cfg.tab_books_videos
            scope_param = cfg.scope_books_videos

        params: dict[str, Any] = {
            "vid": cfg.vid,
            "tab": tab,
            "scope": scope_param,
            "q": f"{field},contains,{query}",
            "offset": str(offset),
            "limit": str(limit),
            "lang": cfg.language,
            "sortby": sort_by,
            "pcAvailability": "true",
        }

        # Facet filters
        q_include: list[str] = []
        if resource_type:
            q_include.append(f"facet_rtype,exact,{resource_type}")
        date_range = _date_range_facet_value(date_from, date_to)
        if date_range:
            q_include.append(f"facet_searchcreationdate,exact,{date_range}")
        if peer_reviewed:
            q_include.append("facet_tlevel,exact,peer_reviewed")

        # Add all qInclude params
        if q_include:
            params["qInclude"] = "|,|".join(q_include)

        data = await self._get("/pnxs", params=params)
        return SearchResponse.from_api_response(data)

    async def get_record(self, record_id: str) -> PrimoRecord | None:
        """Fetch a single record by its Primo record ID.

        Searches by the record ID and returns the first matching result.
        Returns None if not found.
        """
        search_plan = self._record_search_plan(record_id)
        first_fallback: PrimoRecord | None = None

        for tab, scope_param, query in search_plan:
            params: dict[str, Any] = {
                "vid": self._config.vid,
                "tab": tab,
                "scope": scope_param,
                "q": f"any,contains,{query}",
                "offset": "0",
                "limit": "5",
                "lang": self._config.language,
            }
            data = await self._get("/pnxs", params=params)
            response = SearchResponse.from_api_response(data)

            for record in response.records:
                if self._record_ids_match(record.record_id, record_id):
                    return record

            if first_fallback is None and response.records:
                first_fallback = response.records[0]

        return first_fallback

    def _record_search_plan(self, record_id: str) -> list[tuple[str, str, str]]:
        """Return the search attempts used to resolve a Primo record ID."""
        rid = record_id.strip()
        normalised = _normalise_alma_id(rid)

        if rid.lower().startswith("alma") or rid.isdigit():
            queries = [rid]
            if normalised != rid:
                queries.append(normalised)
            alma_prefixed = f"alma{normalised}" if normalised.isdigit() else normalised
            if alma_prefixed not in queries:
                queries.append(alma_prefixed)
            return [
                (self._config.tab_catalogue, self._config.scope_local, query)
                for query in queries
            ] + [
                (self._config.tab_everything, self._config.scope_combined, query)
                for query in queries
            ]

        return [(self._config.tab_everything, self._config.scope_combined, rid)]

    @staticmethod
    def _record_ids_match(found_id: str, requested_id: str) -> bool:
        """Match exact IDs or equivalent Alma IDs with/without prefix."""
        found = found_id.strip()
        requested = requested_id.strip()
        return (
            found == requested
            or _normalise_alma_id(found) == _normalise_alma_id(requested)
        )

    async def suggest(self, query: str) -> list[str]:
        """Get autocomplete suggestions for a search term."""
        cfg = self._config
        params = {
            "vid": cfg.vid,
            "q": query,
            "lang": cfg.language,
        }
        data = await self._get("/suggest", params=params)

        # Extract suggestion texts
        response = data.get("response", {})
        docs = response.get("docs", [])
        return [doc.get("text", "") for doc in docs if doc.get("text")]

    async def get_records(self, record_ids: list[str]) -> list[PrimoRecord]:
        """Fetch multiple records by their IDs."""
        records = []
        for rid in record_ids:
            record = await self.get_record(rid)
            if record:
                records.append(record)
        return records

    async def _get(self, path: str, params: dict[str, Any]) -> dict:
        """Make a GET request to the Primo API."""
        try:
            response = await self._http.get(path, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException as e:
            raise PrimoAPIError(
                f"Request timed out after {self._config.request_timeout}s. "
                "The Primo API may be slow or unavailable. Try again shortly.",
            ) from e
        except httpx.ConnectError as e:
            raise PrimoAPIError(
                f"Could not connect to {self._config.base_url}. "
                "Check your network connection and that the Primo API is available.",
            ) from e
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 400:
                raise PrimoAPIError(
                    f"Bad request (HTTP 400). Check your search query and parameters.",
                    status_code=400,
                ) from e
            elif status >= 500:
                raise PrimoAPIError(
                    f"Primo API server error (HTTP {status}). "
                    "The service may be experiencing issues. Try again later.",
                    status_code=status,
                ) from e
            else:
                raise PrimoAPIError(
                    f"Primo API returned HTTP {status}.",
                    status_code=status,
                ) from e
        except Exception as e:
            raise PrimoAPIError(
                f"Unexpected error querying Primo: {e}",
            ) from e
