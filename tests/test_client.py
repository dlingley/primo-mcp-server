"""Tests for Primo API client request construction."""

from __future__ import annotations

import httpx
import pytest

from primo_mcp_server.client import PrimoAPIError, PrimoClient, _normalise_scope
from primo_mcp_server.config import PrimoConfig


def _config() -> PrimoConfig:
    return PrimoConfig(
        base_url="https://example.test/primaws/rest/pub",
        vid="TEST:VID",
        tab_catalogue="Catalogue",
        tab_everything="Everything",
        tab_books_videos="booksandvideos",
        scope_local="MyInstitution",
        scope_combined="MyInst_and_CI",
        scope_books_videos="BooksVideos",
    )


def _empty_response() -> httpx.Response:
    return httpx.Response(200, json={"info": {"total": 0}, "docs": []})


class TestScopeResolution:
    def test_scope_aliases(self):
        assert _normalise_scope("catalog") == "catalogue"
        assert _normalise_scope("my_institution") == "catalogue"
        assert _normalise_scope("all") == "everything"
        assert _normalise_scope("myinst_and_ci") == "everything"
        assert _normalise_scope("books/videos") == "books_videos"
        assert _normalise_scope("books & videos") == "books_videos"
        assert _normalise_scope("booksandvideos") == "books_videos"

    def test_invalid_scope_raises_clear_error(self):
        with pytest.raises(PrimoAPIError, match='Invalid scope "catalogg"'):
            _normalise_scope("catalogg")


class TestSearchRequestScopes:
    @pytest.mark.parametrize(
        ("scope", "expected_tab", "expected_scope"),
        [
            ("catalogue", "Catalogue", "MyInstitution"),
            ("everything", "Everything", "MyInst_and_CI"),
            ("books_videos", "booksandvideos", "BooksVideos"),
            ("BooksVideos", "booksandvideos", "BooksVideos"),
        ],
    )
    async def test_search_maps_scope_to_primo_params(
        self,
        scope: str,
        expected_tab: str,
        expected_scope: str,
    ):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return _empty_response()

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            await client.search("Singapore", scope=scope)

        params = requests[0].url.params
        assert params["tab"] == expected_tab
        assert params["scope"] == expected_scope

    async def test_invalid_scope_does_not_make_request(self):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            return _empty_response()

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            with pytest.raises(PrimoAPIError):
                await client.search("Singapore", scope="catalogg")

        assert requests == []


class TestGetRecord:
    def _alma_doc(self) -> dict:
        return {
            "pnx": {
                "control": {"recordid": ["alma99317560802601"]},
                "display": {"title": ["Anyuan"], "type": ["book"]},
            }
        }

    async def test_get_record_resolves_prefixed_alma_id_with_numeric_lookup(self):
        requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requests.append(request)
            q = request.url.params["q"]
            if q == "any,contains,99317560802601":
                return httpx.Response(
                    200,
                    json={"info": {"total": 1}, "docs": [self._alma_doc()]},
                )
            return _empty_response()

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            record = await client.get_record("alma99317560802601")

        assert record is not None
        assert record.record_id == "alma99317560802601"
        assert requests[0].url.params["scope"] == "MyInstitution"
        assert requests[1].url.params["q"] == "any,contains,99317560802601"

    async def test_get_record_resolves_numeric_alma_id(self):
        def handler(request: httpx.Request) -> httpx.Response:
            q = request.url.params["q"]
            if q == "any,contains,99317560802601":
                return httpx.Response(
                    200,
                    json={"info": {"total": 1}, "docs": [self._alma_doc()]},
                )
            return _empty_response()

        async with httpx.AsyncClient(
            base_url="https://example.test/primaws/rest/pub",
            transport=httpx.MockTransport(handler),
        ) as http_client:
            client = PrimoClient(http_client, _config())
            record = await client.get_record("99317560802601")

        assert record is not None
        assert record.record_id == "alma99317560802601"
