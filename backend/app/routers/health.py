"""Health check 路由"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    return {
        "status": "ok",
        "version": "0.1.0",
        "chroma_connected": False,   # Phase 1 占位
        "db_connected": True,
    }
