"""BibTeX generation and citation validation helpers."""

import re
from urllib.parse import quote

import httpx
from sqlalchemy.orm import Session

from app.database.sqlite import Paper


def _slug(text: str, limit: int = 32) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "", text.title())
    return slug[:limit] or "paper"


def _entry_type(paper: Paper) -> str:
    venue = (paper.venue or "").lower()
    paper_type = (paper.paper_type or "").lower()
    if "journal" in paper_type or "transactions" in venue or "journal" in venue:
        return "article"
    if "arxiv" in (paper.source or "").lower() or "preprint" in paper_type:
        return "misc"
    return "inproceedings"


def _bib_key(paper: Paper) -> str:
    first_author = "anon"
    if paper.authors:
        first_author = paper.authors[0].split()[-1]
    return f"{_slug(first_author, 14).lower()}{paper.year or 'nd'}{_slug(paper.title, 20)}"


def generate_bibtex(paper_ids: list[str], db: Session) -> dict[str, str]:
    """Generate BibTeX entries for papers."""
    papers = db.query(Paper).filter(Paper.id.in_(paper_ids)).all() if paper_ids else []
    entries = {}
    for paper in papers:
        entry_type = _entry_type(paper)
        venue_field = "journal" if entry_type == "article" else "booktitle"
        fields = {
            "author": " and ".join(paper.authors or []),
            "title": paper.title,
            venue_field: paper.venue or "",
            "year": str(paper.year or ""),
            "doi": paper.doi or "",
            "url": paper.url or paper.pdf_url or "",
        }
        body = "\n".join(
            f"  {key:<9}= {{{value}}},"
            for key, value in fields.items()
            if value
        )
        entries[paper.id] = f"@{entry_type}{{{_bib_key(paper)},\n{body}\n}}"
    return entries


def export_bibliography(paper_ids: list[str], db: Session) -> str:
    """Export a complete .bib file body."""
    return "\n\n".join(generate_bibtex(paper_ids, db).values())


def verify_citations(bibtex_entries: list[str]) -> list[dict]:
    """Validate BibTeX entries by checking DOI with CrossRef, falling back to local format checks."""
    reports = []
    doi_pattern = re.compile(r"doi\s*=\s*[{\"']([^}\"']+)", re.IGNORECASE)

    with httpx.Client(timeout=8) as client:
        for index, entry in enumerate(bibtex_entries, 1):
            doi = doi_pattern.search(entry)
            if not doi:
                reports.append({
                    "index": index,
                    "valid": False,
                    "status": "missing_doi",
                    "message": "No DOI field found.",
                })
                continue

            doi_value = doi.group(1).strip()
            valid_shape = bool(re.match(r"^10\.\d{4,9}/\S+$", doi_value))
            if not valid_shape:
                reports.append({
                    "index": index,
                    "doi": doi_value,
                    "valid": False,
                    "status": "invalid_format",
                    "message": "DOI format is suspicious.",
                })
                continue

            try:
                resp = client.get(f"https://api.crossref.org/works/{quote(doi_value, safe='')}")
                reports.append({
                    "index": index,
                    "doi": doi_value,
                    "valid": resp.status_code == 200,
                    "status": "crossref_found" if resp.status_code == 200 else "crossref_not_found",
                    "message": "CrossRef record found." if resp.status_code == 200 else "CrossRef did not find this DOI.",
                })
            except Exception as exc:
                reports.append({
                    "index": index,
                    "doi": doi_value,
                    "valid": True,
                    "status": "valid_format_unverified",
                    "message": f"DOI format looks valid, but CrossRef check failed: {exc}",
                })
    return reports
