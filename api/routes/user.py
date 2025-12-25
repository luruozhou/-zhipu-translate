"""
用户相关路由
"""

from fastapi import APIRouter, Request

try:
    from api._shared import get_current_user
    from api.services.user_service import UserService
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from api._shared import get_current_user
    from api.services.user_service import UserService

router = APIRouter()


@router.get("/me/usage")
async def get_usage(request: Request):
    """供前端展示当前配额和已用量 - 调用 service 层"""
    authorization = request.headers.get("authorization")
    user = await get_current_user(authorization)
    
    # 调用 service 层获取用量信息
    return UserService.get_usage_info(user)

