"""Smoke tests for MCP tool entrypoints."""

from types import SimpleNamespace

from primo_mcp_server.config import PrimoConfig
from primo_mcp_server.models import PrimoRecord, SearchResponse
from primo_mcp_server.server import primo_get_record, primo_search


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


def _fake_context() -> SimpleNamespace:
    lifespan_context = {
        "client": _FakeClient(),
        "config": PrimoConfig(base_url="https://example.test/primaws/rest/pub"),
    }
    return SimpleNamespace(
        request_context=SimpleNamespace(lifespan_context=lifespan_context)
    )


async def test_primo_search_smoke_does_not_return_unexpected_error():
    output = await primo_search(_fake_context(), "ceo compensation", scope="catalogue")

    assert "Unexpected error" not in output
    assert "Executive Compensation Data" in output


async def test_primo_get_record_smoke_does_not_return_unexpected_error():
    output = await primo_get_record(_fake_context(), "alma123")

    assert "Unexpected error" not in output
    assert "Executive Compensation Data" in output
