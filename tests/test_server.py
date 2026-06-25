"""Smoke tests for MCP tool entrypoints."""

from types import SimpleNamespace

from purduelibrary_mcp_server.config import PrimoConfig
from purduelibrary_mcp_server.models import PrimoRecord, SearchResponse
from purduelibrary_mcp_server.server import primo_cite, primo_export, primo_get_record, primo_search


class _FakeClient:
    async def search(self, **kwargs) -> SearchResponse:
        return SearchResponse.model_validate(
            {
                "info": {"total": 1},
                "records": [
                    PrimoRecord(
                        record_id="alma123",
                        title="Executive Compensation Data",
                        resource_type="database",
                    )
                ],
            }
        )

    async def get_record(self, record_id: str) -> PrimoRecord:
        return PrimoRecord(
            record_id=record_id,
            title="Executive Compensation Data",
            resource_type="database",
        )

    async def get_records(self, record_ids: list[str]) -> list[PrimoRecord]:
        return [
            PrimoRecord(
                record_id=record_id,
                title="Executive Compensation Data",
                resource_type="book",
                creators=["Tan, Mei"],
                creation_date="2024",
            )
            for record_id in record_ids
        ]


def _fake_context() -> SimpleNamespace:
    lifespan_context = {
        "client": _FakeClient(),
        "config": PrimoConfig(
            base_url="https://example.test/primaws/rest/pub",
            _env_file=None,
        ),
    }
    return SimpleNamespace(
        request_context=SimpleNamespace(lifespan_context=lifespan_context)
    )


async def test_primo_search_smoke_does_not_return_unexpected_error():
    output = await primo_search(
        _fake_context(),
        "ceo compensation",
        scope="catalogue",
        include_unavailable=True,
    )

    assert "Unexpected error" not in output
    assert "Queries run:" in output
    assert "- Results found: [any,contains,ceo compensation](" in output
    assert "pcAvailability=true" in output
    assert "Executive Compensation Data" in output


async def test_primo_get_record_smoke_does_not_return_unexpected_error():
    output = await primo_get_record(_fake_context(), "alma123")

    assert "Unexpected error" not in output
    assert "Executive Compensation Data" in output


async def test_primo_cite_accepts_case_insensitive_style():
    output = await primo_cite(_fake_context(), ["alma123"], style="APA7")

    assert "Unexpected error" not in output
    assert "Executive Compensation Data" in output


async def test_primo_export_accepts_case_insensitive_format():
    output = await primo_export(_fake_context(), ["alma123"], format="BibTeX")

    assert "Unexpected error" not in output
    assert "@book{" in output
