"""Smoke tests for MCP tool entrypoints."""

from types import SimpleNamespace

from purduelibrary_mcp_server.config import PrimoConfig
from purduelibrary_mcp_server.models import PrimoRecord, SearchResponse
from purduelibrary_mcp_server.server import primo_cite, primo_export, primo_get_record, primo_search


class _FakeClient:
    def __init__(
        self,
        records: list[PrimoRecord] | None = None,
        records_by_query: dict[str, list[PrimoRecord]] | None = None,
    ):
        self.records = (
            records
            if records is not None
            else [
                PrimoRecord(
                    record_id="alma123",
                    title="Executive Compensation Data",
                    resource_type="database",
                    subjects=["Accounting", "Executive compensation"],
                    keywords=["Corporate governance"],
                )
            ]
        )
        self.records_by_query = records_by_query or {}
        self.search_calls: list[dict] = []

    async def search(self, **kwargs) -> SearchResponse:
        self.search_calls.append(kwargs)
        query = kwargs.get("query", "")
        records = self.records_by_query.get(query, self.records)
        return SearchResponse.model_validate(
            {
                "info": {"total": len(records)},
                "records": records,
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


def _fake_context(client: _FakeClient | None = None) -> SimpleNamespace:
    lifespan_context = {
        "client": client if client is not None else _FakeClient(),
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


async def test_primo_search_zero_results_guides_llm_iteration():
    client = _FakeClient(records=[])

    output = await primo_search(
        _fake_context(client=client),
        "autism",
        resource_type="databases",
    )

    assert [call["query"] for call in client.search_calls] == ["autism"]
    assert 'No results found for "autism".' in output
    assert "Iterative search guidance:" in output
    assert "Try up to five total attempts" in output
    assert "start retries with catalogue databases" in output
    assert 'resource_type="databases"' in output
    assert "direct searches for likely database names" in output
    assert "OR queries for close alternatives" in output
    assert "combine all relevant results found across attempts" in output


def test_primo_search_description_documents_dataset_database_first_policy():
    from purduelibrary_mcp_server.policy import PRIMO_SEARCH_DESCRIPTION

    assert "For dataset or data-source requests" in PRIMO_SEARCH_DESCRIPTION
    assert 'scope="catalogue"' in PRIMO_SEARCH_DESCRIPTION
    assert 'resource_type="databases"' in PRIMO_SEARCH_DESCRIPTION
    assert "to articles or books" in PRIMO_SEARCH_DESCRIPTION


async def test_primo_search_tool_serves_the_policy_description():
    from purduelibrary_mcp_server.policy import PRIMO_SEARCH_DESCRIPTION, SERVER_INSTRUCTIONS
    from purduelibrary_mcp_server.server import mcp

    tools = await mcp.list_tools()
    search_tool = next(t for t in tools if t.name == "primo_search")

    assert search_tool.description == PRIMO_SEARCH_DESCRIPTION
    # The server instructions carry the same single-source policy prose.
    assert "Scope selection policy for callers:" in SERVER_INSTRUCTIONS
    assert "Zero-result policy for callers:" in SERVER_INSTRUCTIONS


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


async def test_primo_search_forwards_compound_clauses_to_client():
    from purduelibrary_mcp_server.query import QueryClause

    client = _FakeClient()
    clauses = [
        QueryClause(field="title", value="capital", connector="AND"),
        QueryClause(field="creator", value="piketty"),
    ]

    output = await primo_search(
        _fake_context(client=client),
        "piketty capital",
        clauses=clauses,
    )

    assert client.search_calls[0]["clauses"] == clauses
    assert "Unexpected error" not in output
