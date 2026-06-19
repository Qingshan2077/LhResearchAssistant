"""Tests for static LaTeX format checks."""

from app.services.format_service import check_format


def _write_main(tmp_path, content: str):
    (tmp_path / "main.tex").write_text(content, encoding="utf-8")
    return tmp_path


def test_neurips_valid_document_has_no_errors(tmp_path):
    project = _write_main(tmp_path, r"""\documentclass[10pt]{article}
\usepackage{neurips_2024}
\begin{document}
\title{Test}\author{Anonymous}\maketitle
\begin{abstract}A concise abstract.\end{abstract}
\bibliographystyle{plainnat}\bibliography{refs}
\end{document}""")
    issues, pages = check_format(str(project), "neurips_2024")
    assert not [issue for issue in issues if issue["severity"] == "error"]
    assert pages >= 1


def test_neurips_reports_missing_abstract(tmp_path):
    project = _write_main(tmp_path, r"""\documentclass[10pt]{article}
\usepackage{neurips_2024}\begin{document}\author{Anonymous}\end{document}""")
    issues, _ = check_format(str(project), "neurips_2024")
    assert any("abstract" in issue["message"].lower() for issue in issues)


def test_neurips_reports_identifying_author(tmp_path):
    project = _write_main(tmp_path, r"""\documentclass[10pt]{article}
\usepackage{neurips_2024}\begin{document}\author{John Doe}
\begin{abstract}Text.\end{abstract}\bibliographystyle{plainnat}\bibliography{r}\end{document}""")
    issues, _ = check_format(str(project), "neurips_2024")
    assert any(issue["rule"] == "anonymity" for issue in issues)


def test_ieee_document_satisfies_required_sections(tmp_path):
    project = _write_main(tmp_path, r"""\documentclass[10pt]{IEEEtran}
\begin{document}\author{Author}\begin{abstract}Text.\end{abstract}
\begin{IEEEkeywords}index terms\end{IEEEkeywords}\bibliography{refs}\end{document}""")
    issues, _ = check_format(str(project), "ieee_trans")
    assert not [issue for issue in issues if issue["severity"] == "error"]


def test_unknown_template_returns_warning(tmp_path):
    project = _write_main(tmp_path, r"\documentclass{article}\begin{document}Hi\end{document}")
    issues, pages = check_format(str(project), "unknown_journal")
    assert issues[0]["rule"] == "venue"
    assert pages == 1


def test_missing_project_returns_path_error(tmp_path):
    issues, pages = check_format(str(tmp_path / "missing"), "neurips_2024")
    assert issues[0]["rule"] == "project_path"
    assert pages == 0
