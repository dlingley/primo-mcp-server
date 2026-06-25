"""Export Primo records to BibTeX, RIS, and CSV formats."""

from __future__ import annotations

import io
import csv
import re

from purduelibrary_mcp_server.models import PrimoRecord


def _record_type_key(resource_type: str) -> str:
    """Normalise Primo record type labels for export mapping."""
    return resource_type.strip().lower().replace("-", "_")


def _bibtex_key(record: PrimoRecord) -> str:
    """Generate a BibTeX citation key from author and year."""
    first_author = ""
    authors = record.display_authors
    if authors:
        # Take last name of first author
        parts = authors[0].split(",", 1)
        first_author = parts[0].strip().lower()
        # Remove non-alphanumeric
        first_author = re.sub(r"[^a-z0-9]", "", first_author)

    year = record.year or "nodate"

    # Add first word of title for uniqueness
    title_word = ""
    if record.title:
        words = re.findall(r"[a-zA-Z]+", record.title)
        if words:
            title_word = words[0].lower()

    if not first_author and not title_word:
        record_key = re.sub(r"[^a-z0-9]", "", record.record_id.lower())
        if record_key:
            return record_key

    return f"{first_author}{year}{title_word}" or "unknown"


def _bibtex_escape(value: str) -> str:
    """Escape special BibTeX characters."""
    replacements = {
        "\\": r"\textbackslash{}",
        "{": r"\{",
        "}": r"\}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
    }
    return "".join(replacements.get(char, char) for char in value)


def _ris_value(value: str) -> str:
    """Collapse newlines in RIS field values so records stay one field per line."""
    return re.sub(r"\s+", " ", value).strip()


def _append_ris(lines: list[str], tag: str, value: str) -> None:
    """Append a non-empty RIS field with whitespace-safe content."""
    cleaned = _ris_value(value)
    if cleaned:
        lines.append(f"{tag}  - {cleaned}")


def export_bibtex(records: list[PrimoRecord]) -> str:
    """Export records as BibTeX entries."""
    entries = []
    used_keys: set[str] = set()

    for record in records:
        # Determine entry type
        rtype = _record_type_key(record.resource_type)
        if rtype in (
            "article",
            "articles",
            "review",
            "reviews",
            "newspaper_article",
            "newspaper_articles",
        ):
            entry_type = "article"
        elif rtype in ("conference_proceeding", "conference_proceedings"):
            entry_type = "inproceedings"
        elif rtype in ("dissertation", "dissertations", "thesis", "theses"):
            entry_type = "phdthesis"
        else:
            entry_type = "book"

        # Generate unique key
        key = _bibtex_key(record)
        if key in used_keys:
            i = 2
            while f"{key}{chr(96+i)}" in used_keys:
                i += 1
            key = f"{key}{chr(96+i)}"
        used_keys.add(key)

        # Build fields
        fields = []
        authors = record.display_authors
        if authors:
            fields.append(f"  author = {{{_bibtex_escape(' and '.join(authors))}}}")
        fields.append(f"  title = {{{_bibtex_escape(record.title)}}}")

        year = record.year
        if year:
            fields.append(f"  year = {{{year}}}")

        if record.journal_title and entry_type == "article":
            fields.append(f"  journal = {{{_bibtex_escape(record.journal_title)}}}")
        if record.volume:
            fields.append(f"  volume = {{{record.volume}}}")
        if record.issue:
            fields.append(f"  number = {{{record.issue}}}")
        if record.start_page:
            pages = record.start_page
            if record.end_page:
                pages += f"--{record.end_page}"
            fields.append(f"  pages = {{{pages}}}")
        if record.publisher:
            fields.append(f"  publisher = {{{_bibtex_escape(record.publisher)}}}")
        if record.doi:
            fields.append(f"  doi = {{{record.doi}}}")
        if record.isbn:
            fields.append(f"  isbn = {{{record.isbn[0]}}}")
        if record.issn:
            fields.append(f"  issn = {{{record.issn[0]}}}")

        entry = f"@{entry_type}{{{key},\n" + ",\n".join(fields) + "\n}"
        entries.append(entry)

    return "\n\n".join(entries)


def export_ris(records: list[PrimoRecord]) -> str:
    """Export records as RIS (Research Information Systems) format."""
    entries = []

    for record in records:
        lines = []

        # Type
        rtype = _record_type_key(record.resource_type)
        ris_type_map = {
            "article": "JOUR",
            "articles": "JOUR",
            "review": "JOUR",
            "reviews": "JOUR",
            "book": "BOOK",
            "books": "BOOK",
            "journal": "JFULL",
            "journals": "JFULL",
            "conference_proceeding": "CONF",
            "conference_proceedings": "CONF",
            "dissertation": "THES",
            "dissertations": "THES",
            "thesis": "THES",
            "theses": "THES",
            "newspaper_article": "NEWS",
            "newspaper_articles": "NEWS",
        }
        lines.append(f"TY  - {ris_type_map.get(rtype, 'GEN')}")

        # Authors
        authors = record.display_authors
        for author in authors:
            _append_ris(lines, "AU", author)

        _append_ris(lines, "TI", record.title)

        if record.journal_title:
            _append_ris(lines, "JO", record.journal_title)
            _append_ris(lines, "T2", record.journal_title)

        year = record.year
        if year:
            _append_ris(lines, "PY", year)
            _append_ris(lines, "DA", record.creation_date)

        if record.volume:
            _append_ris(lines, "VL", record.volume)
        if record.issue:
            _append_ris(lines, "IS", record.issue)
        if record.start_page:
            _append_ris(lines, "SP", record.start_page)
        if record.end_page:
            _append_ris(lines, "EP", record.end_page)

        if record.publisher:
            _append_ris(lines, "PB", record.publisher)

        if record.doi:
            _append_ris(lines, "DO", record.doi)
        if record.isbn:
            _append_ris(lines, "SN", record.isbn[0])
        elif record.issn:
            _append_ris(lines, "SN", record.issn[0])

        if record.description:
            _append_ris(lines, "AB", record.description)

        for subject in record.subjects:
            _append_ris(lines, "KW", subject)

        if record.language:
            _append_ris(lines, "LA", record.language)

        lines.append("ER  - ")
        entries.append("\n".join(lines))

    return "\n\n".join(entries)


def export_csv(records: list[PrimoRecord]) -> str:
    """Export records as CSV with UTF-8-sig encoding (BOM for Excel)."""
    output = io.StringIO()
    # Write BOM for Excel compatibility
    output.write("\ufeff")

    writer = csv.writer(output)
    writer.writerow([
        "Record ID",
        "Title",
        "Authors",
        "Year",
        "Type",
        "Journal",
        "Volume",
        "Issue",
        "Pages",
        "DOI",
        "ISBN",
        "ISSN",
        "Publisher",
        "Subjects",
        "Peer-Reviewed",
        "Language",
    ])

    for record in records:
        authors = record.display_authors
        year = record.year
        pages = record.start_page
        if pages and record.end_page:
            pages += f"-{record.end_page}"

        writer.writerow([
            record.record_id,
            record.title,
            "; ".join(authors),
            year,
            record.resource_type,
            record.journal_title,
            record.volume,
            record.issue,
            pages or "",
            record.doi,
            "; ".join(record.isbn),
            "; ".join(record.issn),
            record.publisher,
            "; ".join(record.subjects),
            "Yes" if record.peer_reviewed else "No",
            record.language,
        ])

    return output.getvalue()
