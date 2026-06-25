"""Tests for Primo configuration defaults."""

from __future__ import annotations

from purduelibrary_mcp_server.config import PrimoConfig


def test_default_config_is_purdue(monkeypatch):
    for key in (
        "PRIMO_BASE_URL",
        "PRIMO_DISCOVERY_BASE_URL",
        "PRIMO_VID",
        "PRIMO_INSTITUTION_NAME",
        "PRIMO_TAB_EVERYTHING",
        "PRIMO_TAB_CATALOGUE",
        "PRIMO_TAB_BOOKS_VIDEOS",
        "PRIMO_SCOPE_COMBINED",
        "PRIMO_SCOPE_LOCAL",
        "PRIMO_SCOPE_BOOKS_VIDEOS",
    ):
        monkeypatch.delenv(key, raising=False)

    config = PrimoConfig(_env_file=None)

    assert config.base_url == "https://purdue.primo.exlibrisgroup.com/primaws/rest/pub"
    assert config.discovery_base_url is None
    assert config.vid == "01PURDUE_PUWL:PURDUE"
    assert config.institution_name == "Purdue University"
    assert config.tab_catalogue == "Catalogue"
    assert config.tab_everything == "Everything"
    assert config.tab_books_videos == "booksandvideos"
    assert config.scope_local == "MyInstitution"
    assert config.scope_combined == "MyInst_and_CI"
    assert config.scope_books_videos == "BooksVideos"
