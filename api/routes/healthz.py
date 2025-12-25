"""
健康检查路由
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz")
async def healthz():
    """健康检查。"""
    return {"status": "ok"}

