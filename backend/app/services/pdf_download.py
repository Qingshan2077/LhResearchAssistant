"""PDF download helpers — download from external URLs to local cache."""

import uuid
from pathlib import Path

import httpx
from pydantic import BaseModel

from app.config import settings


class PdfDownloadResult(BaseModel):
    success: bool
    local_path: str | None = None
    error: str = ""


async def download_pdf(pdf_url: str, title: str = "") -> PdfDownloadResult:
    """Download a PDF from an external URL to the local cache.
    Returns a structured result so callers can surface failures.
    """
    if not pdf_url:
        return PdfDownloadResult(success=False, error="No PDF URL available.")

    # 只处理 HTTP/HTTPS 链接
    if not pdf_url.startswith(("http://", "https://")):
        return PdfDownloadResult(success=False, error="Unsupported PDF URL.")

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
                return PdfDownloadResult(success=False, error=f"URL did not return a PDF ({content_type or 'unknown content type'}).")

            cache_path.write_bytes(resp.content)
            return PdfDownloadResult(success=True, local_path=str(cache_path))

    except httpx.ConnectError:
        return PdfDownloadResult(success=False, error="PDF source is unreachable.")
    except httpx.TimeoutException:
        return PdfDownloadResult(success=False, error="PDF download timed out.")
    except httpx.HTTPStatusError as exc:
        return PdfDownloadResult(success=False, error=f"PDF source returned HTTP {exc.response.status_code}.")
    except Exception as exc:
        return PdfDownloadResult(success=False, error=str(exc)[:120])


async def download_pdf_sync(pdf_url: str, title: str = "") -> PdfDownloadResult:
    """同步版（用于非 async 上下文）。
    batch_create_papers 改为 async 后，不再需要此函数。
    """
    return await download_pdf(pdf_url, title)
