"""LaTeX template and project helpers."""

import shutil
import sys
import uuid
from pathlib import Path

from app.config import settings

def _template_root() -> Path:
    bundled_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2])) / "templates"
    if bundled_root.exists():
        return bundled_root
    return Path(__file__).resolve().parents[2] / "templates"


TEMPLATE_ROOT = _template_root()

DISPLAY_NAMES = {
    "neurips_2024": "NeurIPS 2024",
    "acl": "ACL",
    "ctex_article": "中文 CTeX Article",
    "ieee_trans": "IEEE Transactions",
}

LANGUAGES = {
    "ctex_article": "zh",
}


def list_templates() -> list[dict]:
    """List available LaTeX template folders."""
    if not TEMPLATE_ROOT.exists():
        return []

    templates = []
    for item in sorted(TEMPLATE_ROOT.iterdir()):
        if not item.is_dir() and item.suffix.lower() != ".zip":
            continue
        name = item.stem if item.is_file() else item.name
        templates.append({
            "name": name,
            "display_name": DISPLAY_NAMES.get(name, name.replace("_", " ").title()),
            "language": LANGUAGES.get(name, "en"),
        })
    return templates


def create_project(template: str, title: str, author: str = "") -> str:
    """Create a LaTeX project folder from a template and return its path."""
    safe_title = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in title).strip("_")
    project_name = f"{safe_title or 'paper'}-{uuid.uuid4().hex[:8]}"
    target_dir = Path(settings.writing_projects_dir) / project_name
    target_dir.mkdir(parents=True, exist_ok=True)

    template_path = TEMPLATE_ROOT / template
    if template_path.exists() and template_path.is_dir():
        shutil.copytree(template_path, target_dir, dirs_exist_ok=True)
    else:
        _write_default_template(target_dir, title, author)

    main_tex = target_dir / "main.tex"
    if main_tex.exists():
        content = main_tex.read_text(encoding="utf-8")
        content = content.replace("{{TITLE}}", title).replace("{{AUTHOR}}", author or "Author")
        main_tex.write_text(content, encoding="utf-8")

    (target_dir / "figures").mkdir(exist_ok=True)
    (target_dir / "bib").mkdir(exist_ok=True)
    if not (target_dir / "bibliography.bib").exists():
        (target_dir / "bibliography.bib").write_text("% Add BibTeX entries here\n", encoding="utf-8")

    return str(target_dir)


def list_project_files(project_path: str) -> list[dict]:
    root = Path(project_path)
    if not root.exists():
        return []

    files = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root).as_posix()
        files.append({
            "path": rel,
            "type": "directory" if path.is_dir() else "file",
            "size": path.stat().st_size if path.is_file() else 0,
        })
    return files


def _write_default_template(target_dir: Path, title: str, author: str) -> None:
    (target_dir / "main.tex").write_text(
        rf"""\documentclass{{article}}
\usepackage[utf8]{{inputenc}}
\usepackage{{natbib}}
\usepackage{{graphicx}}

\title{{{title}}}
\author{{{author or "Author"}}}
\date{{\today}}

\begin{{document}}
\maketitle

\begin{{abstract}}
Write the abstract here.
\end{{abstract}}

\section{{Introduction}}

\section{{Method}}

\section{{Experiments}}

\section{{Conclusion}}

\bibliographystyle{{plainnat}}
\bibliography{{bibliography}}
\end{{document}}
""",
        encoding="utf-8",
    )
