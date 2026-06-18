# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for packaging the Research Assistant backend as a standalone EXE.
Run on Windows:  pyinstaller pack.spec

ChromaDB is tricky with PyInstaller due to native extensions + dynamic imports.
If you get import errors at runtime, add hidden imports below and retry.
"""

import os
import sys
from pathlib import Path

# ── Block 1: Collect all data files ChromaDB needs ──────────────────────────
# ChromaDB ships compiled native modules that PyInstaller can't auto-detect.
# We collect from site-packages/chromadb/ recursively.
import chromadb
_chromadb_root = Path(chromadb.__file__).parent

# ── Block 2: Application settings ───────────────────────────────────────────
block_cipher = None

a = Analysis(
    ['app/main.py'],
    pathex=[],
    binaries=[],
    datas=[
        # ChromaDB native data files (compiled .so/.pyd + migrations)
        (str(_chromadb_root / 'api'), 'chromadb/api'),
        (str(_chromadb_root / 'db'), 'chromadb/db'),
        (str(_chromadb_root / 'migrations'), 'chromadb/migrations'),
    ],
    hiddenimports=[
        # ── App modules ──
        'app',
        'app.main',
        'app.config',
        'app.database',
        'app.database.sqlite',
        'app.database.chroma_client',
        'app.database.usage_tracker',
        'app.llm',
        'app.llm.router',
        'app.llm.providers',
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

        # ── FastAPI / uvicorn ──
        'uvicorn',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.middleware',
        'uvicorn.middleware.wsgi',
        'fastapi',
        'fastapi.routing',
        'fastapi.openapi',
        'sse_starlette',

        # ── SQLAlchemy ──
        'sqlalchemy',
        'sqlalchemy.sql.default_comparator',
        'sqlalchemy.dialects.sqlite',

        # ── ChromaDB (the pain points) ──
        'chromadb',
        'chromadb.api',
        'chromadb.api.fastapi',
        'chromadb.api.segment',
        'chromadb.db.impl.sqlite',
        'chromadb.db.impl.grpc',
        'chromadb.telemetry',
        'chromadb.telemetry.posthog',
        'chromadb.quota',
        'chromadb.rate_limiting',
        'chromadb.auth',
        'chromadb.auth.token_auth',
        'chromadb.utils.embedding_functions',
        'chromadb.api.models.Collection',

        # ── HTTP / async ──
        'httpx',
        'httpx._transports',
        'httpx._auth',
        'aiofiles',
        'websockets',
        'websockets.legacy',
        'websockets.legacy.server',
        'websockets.legacy.client',
        'python_multipart',

        # ── ArXiv ──
        'arxiv',
        'arxiv.arxiv',

        # ── OpenAI / LangGraph ──
        'openai',
        'openai.resources',
        'openai.resources.chat',
        'openai.resources.chat.completions',
        'langgraph',
        'langgraph.graph',
        'langgraph.checkpoint',

        # ── PyMuPDF ──
        'fitz',
        'fitz.utils',

        # ── Other ──
        'pydantic',
        'pydantic_settings',
        'yaml',
        'json',
        'csv',
        'xml',
        'xml.etree',
        'xml.etree.ElementTree',
        'email',
        'email.mime',
        'email.mime.multipart',
        'email.mime.text',
        'http',
        'http.client',
        'urllib',
        'urllib.parse',
        'asyncio',
        'concurrent',
        'concurrent.futures',
        'multipart',
        'multiprocessing',
        'multiprocessing.connection',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
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

# ── Block 3: Collect all packages ──────────────────────────────────────────
# ChromaDB + uvicorn have many submodules that need recursive collection
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

# ── Block 4: Bundle into a single directory (--onedir) ─────────────────────
# Use ONEDIR for faster startup and easier debugging; switch to ONEFILE only
# if you specifically need a single .exe (slower startup).
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='research-backend',
)
