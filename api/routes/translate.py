"""
翻译路由
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

try:
    from api._shared import get_current_user
    from api.services.translate_service import TranslateService
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from api._shared import get_current_user
    from api.services.translate_service import TranslateService

router = APIRouter()


class TranslateRequest(BaseModel):
    text: str
    target_lang: str = "英文"


class TranslateResponse(BaseModel):
    translated_text: str
    estimated_tokens: int
    remaining_tokens: int


@router.post("/translate")
async def translate(request: Request, body: TranslateRequest):
    """翻译接口 - 调用 service 层处理业务逻辑"""
    authorization = request.headers.get("authorization")
    user = await get_current_user(authorization)
    
    try:
        # 调用 service 层处理翻译业务逻辑
        translated_text, estimated_tokens, remaining_tokens = await TranslateService.translate_text(
            user=user,
            text=body.text,
            target_lang=body.target_lang
        )
        
        return TranslateResponse(
            translated_text=translated_text,
            estimated_tokens=estimated_tokens,
            remaining_tokens=remaining_tokens,
        )
    except ValueError as e:
        # 业务逻辑错误（如额度不足）
        raise HTTPException(status_code=402, detail=str(e))
    except RuntimeError as e:
        # 翻译服务错误
        raise HTTPException(status_code=500, detail=str(e))

