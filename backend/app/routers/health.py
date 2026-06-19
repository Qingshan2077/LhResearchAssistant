"""Health check route."""

from fastapi import APIRouter

from app.version import __version__

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "version": __version__,
        "chroma_connected": False,
        "db_connected": True,
    }
