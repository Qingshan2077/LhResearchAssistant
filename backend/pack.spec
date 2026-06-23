# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for packaging the Research Assistant backend as a standalone EXE.
Run on Windows:  pyinstaller pack.spec --clean --noconfirm

Uses collect_all() for packages with dynamic imports (SQLAlchemy, ChromaDB, etc.)
to ensure all submodules are bundled.
"""
import os
from pathlib import Path

# ── Force PyInstaller to collect entire packages (not just traced deps) ──────
# These packages use dynamic/importlib imports that static analysis can't trace.
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

# ── Pre-collect per-package ─────────────────────────────────────────────────
# collect_all() returns (mods: list[str], datas: list[tuple], binaries: list[tuple])

def _pkg(pkg_name):
    """Collect all modules, data, and binaries for a package."""
    mods = collect_submodules(pkg_name)
    datas = collect_data_files(pkg_name, include_py_files=True)
    return mods, datas

# Critical: SQLAlchemy (ORM + engine + dialects + SQL)
_sa_mods, _sa_datas = _pkg("sqlalchemy")

# ChromaDB native components
_cdb_mods, _cdb_datas = _pkg("chromadb")

# FastAPI / starlette / pydantic
_fa_mods, _fa_datas = _pkg("fastapi")
_pd_mods, _pd_datas = _pkg("pydantic")

# Others known to have dynamic imports
_uv_mods, _uv_datas = _pkg("uvicorn")

# ── Application analysis ────────────────────────────────────────────────────
block_cipher = None
_spec_root = Path(globals().get("SPECPATH", os.getcwd())).resolve()

# ChromaDB root for extra data files
import chromadb as _chromadb_mod
_chromadb_root = Path(_chromadb_mod.__file__).parent

a = Analysis(
    ['app/main.py'],
    pathex=[],
    binaries=[],
    datas=(
        # ChromaDB migrations (critical for startup)
        [
            (str(_chromadb_root / 'migrations'), 'chromadb/migrations'),
            (str(_spec_root / 'alembic.ini'), '.'),
            (str(_spec_root / 'alembic'), 'alembic'),
        ]
        + _sa_datas
        + _cdb_datas
        + _fa_datas
        + _pd_datas
        + _uv_datas
    ),
    hiddenimports=(
        # ── App modules ──
        [
            'app',
            'app.main',
            'app.config',
            'app.database',
            'app.database.sqlite',
            'app.database.chroma_client',
            'app.database.usage_tracker',
            'app.llm',
            'app.llm.router',
            # providers are individual files under app/llm/ (deepseek, openai_compat, ollama)
            'app.agents',
            'app.agents.review_agent',
            'app.agents.idea_agent',
            'app.agents.socratic_agent',
            'app.agents.failure_checklist_agent',
            'app.services',
            'app.services.search_service',
            'app.services.pdf_download',
            'app.services.citation_graph',
            'app.services.comparison_matrix',
            'app.services.s2_client',
            'app.services.paper_sources',
            'app.services.paper_sources.dblp',
            'app.routers',
            'app.routers.papers',
            'app.routers.search',
            'app.routers.settings',
            'app.routers.review',
            'app.routers.socratic',
            'app.routers.verification',
            'app.models',
            'app.models.__init__',

            # ── Core infra (explicit, in case collect_all misses something) ──
            'alembic',
            'anyio',
            'click',
            'colorama',
            'h11',
            'httpcore',
            'idna',
            'sniffio',
            'starlette',
            'typing_extensions',

            # ── HTTP / async ──
            'httpx',
            'aiofiles',
            'websockets',
            'python_multipart',
            'sse_starlette',

            # ── ArXiv ──
            'arxiv',

            # ── OpenAI / LangGraph ──
            'openai',
            'langgraph',

            # ── PyMuPDF ──
            'fitz',

            # ── Standard lib that might be missed ──
            'email.mime',
            'email.mime.multipart',
            'email.mime.text',
            'xml.etree',
            'xml.etree.ElementTree',
            'concurrent',
            'concurrent.futures',
            'multipart',
            'multiprocessing',
        ]
        + _sa_mods
        + _cdb_mods
        + _fa_mods
        + _pd_mods
        + _uv_mods
    ),
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'pandas',
        'notebook',
        'jupyter',
        'ipykernel',
        'IPython',
        'PIL.ImageShow',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
    ],
    noarchive=False,
)

# ── Build single-file EXE (--onefile) ───────────────────────────────────────
# ONEfile is preferred for Tauri sidecar — a single .exe is easier to bundle.
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='research-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # No console window for production
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='research-backend.ico' if os.path.exists('research-backend.ico') else None,
)
