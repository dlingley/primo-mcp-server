"""Tests for Primo PNX model parsing."""

from primo_mcp_server.models import PrimoRecord, SearchResponse


class TestSearchResponse:
    def test_parse_search_results(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        assert response.info.total > 0
        assert len(response.records) == 3

    def test_parse_empty_results(self, empty_results_data):
        response = SearchResponse.from_api_response(empty_results_data)
        assert response.info.total == 0
        assert len(response.records) == 0

    def test_total_count_compatibility_properties(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        assert response.total_results == response.info.total
        assert response.total_local_results == response.info.total_local
        assert response.total_pc_results == response.info.total_pc

    def test_record_has_title(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        for record in response.records:
            assert record.title != ""

    def test_record_has_creators(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        for record in response.records:
            assert len(record.creators) > 0

    def test_record_has_type(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        for record in response.records:
            assert record.resource_type == "article"

    def test_record_has_record_id(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        for record in response.records:
            assert record.record_id != ""

    def test_peer_reviewed_detected(self, search_results_data):
        response = SearchResponse.from_api_response(search_results_data)
        # At least one record should be peer-reviewed
        assert any(r.peer_reviewed for r in response.records)


class TestPrimoRecord:
    def test_from_minimal_doc(self):
        """Test parsing with minimal/missing fields."""
        doc = {
            "pnx": {
                "display": {"title": ["Test Title"]},
                "control": {"recordid": ["test123"]},
            }
        }
        record = PrimoRecord.from_api_doc(doc)
        assert record.title == "Test Title"
        assert record.record_id == "test123"
        assert record.creators == []
        assert record.doi == ""

    def test_doi_extraction(self):
        doc = {
            "pnx": {
                "display": {
                    "title": ["Test"],
                    "identifier": ["ISSN: 1234-5678", "DOI: 10.1234/test"],
                },
                "control": {"recordid": ["test"]},
            }
        }
        record = PrimoRecord.from_api_doc(doc)
        assert record.doi == "10.1234/test"


class TestNameCleaning:
    def test_strips_subfield_markers_from_creators(self):
        doc = {
            "pnx": {
                "display": {
                    "title": ["AI"],
                    "creator": ["Mueller, John, 1958- author.$$QMueller, John"],
                },
                "control": {"recordid": ["r1"]},
            }
        }
        record = PrimoRecord.from_api_doc(doc)
        assert record.creators == ["Mueller, John, 1958-"]
        assert all("$$" not in c for c in record.creators)

    def test_strips_relator_from_contributors(self):
        doc = {
            "pnx": {
                "display": {
                    "title": ["AI"],
                    "contributor": [
                        "Solo, Ashu M. G., editor.$$QSolo, Ashu M. G.",
                        "Arabnia, Hamid R., editor.$$QArabnia, Hamid R.",
                    ],
                },
                "control": {"recordid": ["r2"]},
            }
        }
        record = PrimoRecord.from_api_doc(doc)
        assert record.contributors == ["Solo, Ashu M. G.", "Arabnia, Hamid R."]

    def test_display_authors_prefers_structured(self):
        doc = {
            "pnx": {
                "display": {"title": ["AI"], "creator": ["Noise$$Qx"]},
                "addata": {"au": ["Clean, Author"]},
                "control": {"recordid": ["r3"]},
            }
        }
        record = PrimoRecord.from_api_doc(doc)
        assert record.display_authors == ["Clean, Author"]

    def test_display_authors_falls_back_to_addau(self):
        # Edited book: no au, no display.creator, but addau (editors) present.
        doc = {
            "pnx": {
                "display": {
                    "title": ["AI"],
                    "contributor": ["Solo, Ashu M. G., editor.$$QSolo, Ashu M. G."],
                },
                "addata": {"addau": ["Solo, Ashu M. G.", "Arabnia, Hamid R."]},
                "control": {"recordid": ["r4"]},
            }
        }
        record = PrimoRecord.from_api_doc(doc)
        assert record.authors_structured == []
        assert record.display_authors == ["Solo, Ashu M. G.", "Arabnia, Hamid R."]

    def test_unknown_author_when_no_names(self):
        doc = {"pnx": {"display": {"title": ["A journal"]}, "control": {"recordid": ["r5"]}}}
        record = PrimoRecord.from_api_doc(doc)
        assert record.display_authors == []

    def test_year_extracted_from_messy_dates(self):
        for raw, expected in [
            ("2021", "2021"),
            ("2021-03", "2021"),
            ("c1996", "1996"),
            ("[2019]", "2019"),
            ("1992-2000", "1992"),
            ("n.d.", ""),
        ]:
            doc = {
                "pnx": {
                    "display": {"title": ["T"], "creationdate": [raw]},
                    "control": {"recordid": ["r"]},
                }
            }
            assert PrimoRecord.from_api_doc(doc).year == expected, raw

    def test_preserves_chinese_metadata_and_splits_full_width_separator(self):
        title = "\u5b89\u6e90 : \u767c\u6398\u4e2d\u570b\u9769\u547d\u4e4b\u50b3\u7d71."
        author = "\u88f4, \u5b9c\u7406."
        contributor = "\u95bb, \u5c0f\u99ff."
        publisher = "\u9999\u6e2f : \u9999\u6e2f\u5927\u5b78\u51fa\u7248\u793e"
        communism = "\u5171\u7522\u4e3b\u7fa9"
        china = "\u4e2d\u570b"
        doc = {
            "pnx": {
                "display": {
                    "title": [title],
                    "creator": [f"{author}\uff1b{contributor}"],
                    "contributor": [f"{contributor}$$Q{contributor}"],
                    "publisher": [publisher],
                    "subject": [f"{communism}\uff1b{china}"],
                },
                "control": {"recordid": ["alma99317560802601"]},
            }
        }

        record = PrimoRecord.from_api_doc(doc)

        assert record.title == title
        assert record.creators == [author, contributor]
        assert record.contributors == [contributor]
        assert record.publisher == publisher
        assert record.subjects == [communism, china]

    def test_recovers_chinese_text_from_pure_pnx_subfields(self):
        title = "\u5b89\u6e90"
        author = "\u88f4, \u5b9c\u7406."
        doc = {
            "pnx": {
                "display": {
                    "title": [f"$$N{title}$$Rtitle"],
                    "creator": [f"$$N{author}$$Rauthor"],
                },
                "control": {"recordid": ["alma99317560802601"]},
            }
        }

        record = PrimoRecord.from_api_doc(doc)

        assert record.title == title
        assert record.creators == [author]
