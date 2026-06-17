"""Static LaTeX format checks for writing projects."""

import re
from pathlib import Path


FORMAT_RULES = {
    "neurips_2024": {
        "max_pages": 9,
        "max_references_pages": 1,
        "anonymous": True,
        "required_sections": ["abstract"],
        "max_abstract_words": 200,
        "font_size": "10pt",
        "bibliography_style": "plainnat",
        "template_check": [
            r"\\documentclass(?:\[[^\]]*\])?\{article\}",
            r"\\usepackage(?:\[[^\]]*\])?\{neurips",
        ],
    },
    "acl": {
        "max_pages": 8,
        "anonymous": True,
        "required_sections": ["abstract"],
        "max_abstract_words": 250,
        "bibliography_style": "acl_natbib",
        "template_check": [
            r"\\usepackage(?:\[[^\]]*\])?\{acl",
        ],
    },
    "ieee_trans": {
        "max_pages": 12,
        "anonymous": False,
        "required_sections": ["abstract", "index terms"],
        "font_size": "10pt",
        "template_check": [
            r"\\documentclass(?:\[[^\]]*\])?\{IEEEtran\}",
        ],
    },
    "ctex_article": {
        "max_pages": 15,
        "anonymous": False,
        "language": "zh",
        "required_sections": ["abstract"],
        "template_check": [
            r"\\documentclass(?:\[[^\]]*\])?\{ctexart\}",
        ],
    },
}


def _issue(severity: str, rule: str, message: str, line: int = 0) -> dict:
    return {"severity": severity, "rule": rule, "message": message, "line": line}


def _line_number(content: str, index: int) -> int:
    if index < 0:
        return 0
    return content.count("\n", 0, index) + 1


def _strip_latex(tex_content: str) -> str:
    content = re.sub(r"%.*", " ", tex_content)
    content = re.sub(r"\\(?:section|subsection|subsubsection|title|author)\*?\{[^}]*\}", " ", content)
    content = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^}]*\})?", " ", content)
    content = re.sub(r"[{}$&_^#~]", " ", content)
    return re.sub(r"\s+", " ", content).strip()


def estimate_page_count(tex_content: str) -> int:
    """Roughly estimate compiled page count from LaTeX source length."""
    plain_text = _strip_latex(tex_content)
    latin_words = re.findall(r"[A-Za-z0-9][A-Za-z0-9-]*", plain_text)
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", plain_text)
    weighted_words = len(latin_words) + int(len(cjk_chars) / 1.8)
    figures = len(re.findall(r"\\begin\{figure\}|\\includegraphics", tex_content))
    tables = len(re.findall(r"\\begin\{table\}|\\begin\{tabular\}", tex_content))
    estimated = int((weighted_words / 650) + (figures * 0.35) + (tables * 0.25) + 0.8)
    return max(1, estimated)


def _abstract_word_count(tex_content: str) -> tuple[int, int]:
    match = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", tex_content, re.DOTALL | re.IGNORECASE)
    if not match:
        return 0, 0
    text = _strip_latex(match.group(1))
    latin_words = re.findall(r"[A-Za-z0-9][A-Za-z0-9-]*", text)
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", text)
    return len(latin_words) + int(len(cjk_chars) / 1.8), _line_number(tex_content, match.start())


def _has_required_section(tex_content: str, section: str) -> bool:
    section_lower = section.lower()
    if section_lower == "abstract":
        return bool(re.search(r"\\begin\{abstract\}", tex_content, re.IGNORECASE))
    if section_lower == "index terms":
        return bool(
            re.search(r"\\begin\{IEEEkeywords\}", tex_content, re.IGNORECASE)
            or re.search(r"\\(?:section|subsection)\*?\{Index Terms\}", tex_content, re.IGNORECASE)
            or re.search(r"\\(?:section|subsection)\*?\{Keywords\}", tex_content, re.IGNORECASE)
        )
    return bool(re.search(rf"\\(?:section|subsection)\*?\{{\s*{re.escape(section)}\s*\}}", tex_content, re.IGNORECASE))


def _check_author_anonymity(tex_content: str) -> tuple[bool, int]:
    match = re.search(r"\\author\{(?P<author>.*?)\}", tex_content, re.DOTALL | re.IGNORECASE)
    if not match:
        return True, 0
    author_text = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?(?:\{[^}]*\})?", " ", match.group("author"))
    normalized = re.sub(r"\s+", " ", author_text).strip().lower()
    anonymous_markers = ("anonymous", "submission", "author", "blind", "under review")
    return (not normalized or any(marker in normalized for marker in anonymous_markers)), _line_number(tex_content, match.start())


def check_format(project_path: str, venue: str) -> tuple[list[dict], int]:
    """Check a LaTeX project and return issues plus estimated pages."""
    rules = FORMAT_RULES.get(venue, {})
    issues: list[dict] = []
    root = Path(project_path)
    main_tex = root / "main.tex"

    if not root.exists():
        return [_issue("error", "project_path", "LaTeX project directory does not exist.")], 0
    if not main_tex.exists():
        return [_issue("error", "main_tex", "main.tex was not found in the LaTeX project.")], 0

    tex_content = main_tex.read_text(encoding="utf-8", errors="ignore")
    total_pages = estimate_page_count(tex_content)

    if not rules:
        issues.append(_issue("warning", "venue", f"No built-in format rules for venue '{venue}'."))
        return issues, total_pages

    for pattern in rules.get("template_check", []):
        match = re.search(pattern, tex_content, re.IGNORECASE)
        if not match:
            issues.append(_issue("warning", "template", f"Template pattern not found: {pattern}"))

    max_pages = rules.get("max_pages")
    if max_pages and total_pages > max_pages:
        issues.append(
            _issue(
                "error",
                "page_limit",
                f"Estimated page count is {total_pages}, exceeding the limit of {max_pages} pages.",
            )
        )
    elif max_pages and total_pages >= max_pages:
        issues.append(_issue("info", "page_limit", f"Estimated page count is close to the limit: {total_pages}/{max_pages}."))

    required_sections = rules.get("required_sections", [])
    for section in required_sections:
        if not _has_required_section(tex_content, section):
            issues.append(_issue("error", "required_section", f"Missing required section: {section}."))

    max_abstract_words = rules.get("max_abstract_words")
    if max_abstract_words:
        abstract_words, line = _abstract_word_count(tex_content)
        if abstract_words == 0:
            issues.append(_issue("error", "abstract", "Abstract environment is missing or empty."))
        elif abstract_words > max_abstract_words:
            issues.append(
                _issue(
                    "warning",
                    "abstract_length",
                    f"Abstract has about {abstract_words} words, exceeding the {max_abstract_words}-word guideline.",
                    line,
                )
            )

    if rules.get("anonymous"):
        anonymous, line = _check_author_anonymity(tex_content)
        if not anonymous:
            issues.append(_issue("error", "anonymity", "Author field appears to contain identifying information.", line))

    font_size = rules.get("font_size")
    if font_size:
        docclass = re.search(r"\\documentclass(?:\[(?P<opts>[^\]]*)\])?\{[^}]+\}", tex_content, re.IGNORECASE)
        opts = docclass.group("opts") if docclass else ""
        if docclass and font_size not in (opts or ""):
            issues.append(_issue("warning", "font_size", f"Document class does not explicitly request {font_size}.", _line_number(tex_content, docclass.start())))

    bibliography_style = rules.get("bibliography_style")
    if bibliography_style and not re.search(rf"\\bibliographystyle\{{\s*{re.escape(bibliography_style)}\s*\}}", tex_content):
        issues.append(_issue("warning", "bibliography_style", f"Expected bibliography style '{bibliography_style}'."))

    if not re.search(r"\\bibliography\{[^}]+\}|\\printbibliography", tex_content):
        issues.append(_issue("warning", "bibliography", "No bibliography command was found."))

    return issues, total_pages
