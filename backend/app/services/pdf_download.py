"""PDF download helpers — download from external URLs to local cache."""

import uuid
from pathlib import Path

import httpx

from app.config import settings


async def download_pdf(pdf_url: str, title: str = "") -> str | None:
    """Download a PDF from an external URL to the local cache.
    Returns the local path on success, None on failure.
    """
    if not pdf_url:
        return None

    # 只处理 HTTP/HTTPS 链接
    if not pdf_url.startswith(("http://", "https://")):
        return None

    # 生成缓存文件名
    safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in title[:40])
    file_name = f"{safe_name or 'paper'}-{uuid.uuid4().hex[:8]}.pdf"
    cache_path = Path(settings.papers_cache_dir) / file_name

    try:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            resp = await client.get(pdf_url)
            resp.raise_for_status()

            # 确认是 PDF
            content_type = resp.headers.get("content-type", "")
            if "application/pdf" not in content_type and not content_type.startswith("application/octet"):
                return None

            cache_path.write_bytes(resp.content)
            return str(cache_path)

    except Exception:
        return None


async def download_pdf_sync(pdf_url: str, title: str = "") -> str | None:
    """同步版（用于非 async 上下文）。
    batch_create_papers 改为 async 后，不再需要此函数。
    """
    return await download_pdf(pdf_url, title)
