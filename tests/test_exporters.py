"""Tests for export formats."""

from primo_mcp_server.exporters import export_bibtex, export_csv, export_ris
from primo_mcp_server.models import PrimoRecord, SearchResponse


class TestBibTeX:
    def test_article_export(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        output = export_bibtex(response.records)
        assert "@article{" in output
        assert "author = {" in output
        assert "title = {" in output
        assert "doi = {" in output

    def test_unique_keys(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        output = export_bibtex(response.records)
        # Extract all citation keys
        import re
        keys = re.findall(r"@\w+\{(\w+),", output)
        assert len(keys) == len(set(keys)), "BibTeX keys should be unique"

    def test_chinese_record_uses_stable_ascii_key_and_preserves_text(self):
        title = "\u5b89\u6e90 : \u767c\u6398\u4e2d\u570b\u9769\u547d\u4e4b\u50b3\u7d71."
        author = "\u88f4, \u5b9c\u7406."
        record = PrimoRecord(
            record_id="alma99317560802601",
            title=title,
            resource_type="book",
            creators=[author],
            creation_date="2014",
        )

        output = export_bibtex([record])

        assert "@book{alma99317560802601," in output
        assert f"author = {{{author}}}" in output
        assert f"title = {{{title}}}" in output


class TestRIS:
    def test_article_export(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        output = export_ris(response.records)
        assert "TY  - JOUR" in output
        assert "AU  - " in output
        assert "TI  - " in output
        assert "ER  - " in output

    def test_has_doi(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        output = export_ris(response.records[:1])
        if response.records[0].doi:
            assert "DO  - " in output

    def test_chinese_record_preserved(self):
        title = "\u5b89\u6e90"
        author = "\u88f4, \u5b9c\u7406."
        output = export_ris([
            PrimoRecord(title=title, resource_type="book", creators=[author])
        ])

        assert f"AU  - {author}" in output
        assert f"TI  - {title}" in output


class TestCSV:
    def test_csv_has_header(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        output = export_csv(response.records)
        assert "Record ID" in output
        assert "Title" in output
        assert "Authors" in output

    def test_csv_has_bom(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        output = export_csv(response.records)
        assert output.startswith("\ufeff")

    def test_csv_row_count(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        output = export_csv(response.records)
        lines = output.strip().split("\n")
        # Header + data rows
        assert len(lines) == 1 + len(response.records)

    def test_chinese_record_preserved_with_bom(self):
        title = "\u5b89\u6e90"
        author = "\u88f4, \u5b9c\u7406."
        output = export_csv([
            PrimoRecord(title=title, resource_type="book", creators=[author])
        ])

        assert output.startswith("\ufeff")
        assert title in output
        assert author in output
