"""
backend/main.py

FastAPI 后端：翻译服务 + 用量计费

- 验证前端传来的 Supabase JWT，获取当前用户
- 按月管理每个用户的 token 配额
- 调用智谱 GLM 翻译
- 记录 usage_logs，并更新 users.used_tokens_this_period
"""

import os
import math
import datetime as dt
import json
import time
from typing import Optional, Tuple

import httpx
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from zai import ZhipuAiClient

from pathlib import Path
import sys

# 项目根目录
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))


def load_supabase_config():
    """优先从环境变量读取，其次从项目根目录的 config.json 读取。"""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_service_key:
        config_path = ROOT_DIR / "config.json"
        if config_path.exists():
            import json

            with config_path.open("r", encoding="utf-8") as f:
                cfg = json.load(f)
            supabase_url = supabase_url or cfg.get("SUPABASE_URL")
            # 这里建议使用 service_role key
            supabase_service_key = supabase_service_key or cfg.get("SUPABASE_KEY")

    if not supabase_url or not supabase_service_key:
        raise RuntimeError("缺少 SUPABASE_URL / SUPABASE_SERVICE_KEY，请在环境变量或 config.json 中配置")

    return supabase_url, supabase_service_key


SUPABASE_URL, SUPABASE_SERVICE_KEY = load_supabase_config()


def get_zhipu_client() -> ZhipuAiClient:
    """
    从项目根目录的 config.json 中读取 ZHIPU_API_KEY，并创建 ZhipuAiClient。
    与 glm_4_5_flash_demo 中的逻辑解耦，单独在 backend 内维护。
    """
    config_path = ROOT_DIR / "config.json"
    if not config_path.exists():
        raise RuntimeError("缺少 config.json，用于读取 ZHIPU_API_KEY")

    with config_path.open("r", encoding="utf-8") as f:
        cfg = json.load(f)

    api_key = cfg.get("ZHIPU_API_KEY")
    if not api_key:
        raise RuntimeError("config.json 中缺少 ZHIPU_API_KEY，请检查配置")

    return ZhipuAiClient(api_key=api_key)


def translate_text_sync(text: str, target_lang: str) -> Tuple[bool, str, float]:
    """
    同步版本的翻译函数，在 backend 中单独实现，不依赖外部模块。
    返回: (是否成功, 错误信息或结果, 耗时)
    """
    start_time = time.time()
    try:
        client = get_zhipu_client()
        response = client.chat.completions.create(
            model="GLM-4-Flash-250414",
            messages=[
                {
                    "role": "user",
                    "content": (
                        "你是一个专业的翻译助手。"
                        f"请将我给你的文本翻译成目标语言：{target_lang}。"
                        "目标语言的描述可能是自然语言（例如'简体中文''英语'），"
                        "也可能是语言代码（例如 zh、en、ja、fr 等），"
                        "请根据这个描述自行理解目标语言并进行翻译。"
                        "只输出翻译后的文本本身，不要任何解释或前后缀。"
                    ),
                },
                {
                    "role": "user",
                    "content": text,
                },
            ],
            thinking={"type": "disabled"},
            stream=False,
            max_tokens=2048,
            temperature=0.3,
        )

        result = response.choices[0].message.content
        elapsed = time.time() - start_time
        return True, result, elapsed
    except Exception as e:
        elapsed = time.time() - start_time
        return False, str(e), elapsed


def get_supabase_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


app = FastAPI(title="Translation & Billing API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4000", "http://127.0.0.1:4000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TranslateRequest(BaseModel):
    text: str
    target_lang: str = "英文"


class TranslateResponse(BaseModel):
    translated_text: str
    estimated_tokens: int
    remaining_tokens: int


class AuthedUser(BaseModel):
    auth_user_id: str  # auth.users.id (uuid)
    user_row_id: int   # public.users.id (bigint)
    monthly_quota_tokens: int
    used_tokens_this_period: int
    billing_period_start: dt.date


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
) -> AuthedUser:
    """
    从 Authorization: Bearer <jwt> 中解析 Supabase 用户，
    并在 public.users 中找到对应行（没有则创建）。
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="缺少 Authorization Bearer token")

    access_token = authorization.split(" ", 1)[1]
    sb = get_supabase_client()

    # 调用 Supabase Auth API 获取用户信息
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "apikey": SUPABASE_SERVICE_KEY,
            },
            timeout=10,
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=401, detail="无效的 Supabase 会话")

    auth_user = resp.json()
    auth_user_id = auth_user["id"]  # uuid

    # 映射到 public.users（如果不存在则自动创建）
    data = (
        sb.table("users")
        .select("*")
        .eq("auth_user_id", auth_user_id)
        .execute()
    ).data

    if data:
        row = data[0]
    else:
        profile = {
            "auth_user_id": auth_user_id,
            "name": auth_user.get("user_metadata", {}).get("full_name") or auth_user.get("email"),
        }
        row = sb.table("users").insert(profile).execute().data[0]

    return AuthedUser(
        auth_user_id=auth_user_id,
        user_row_id=row["id"],
        monthly_quota_tokens=row.get("monthly_quota_tokens", 50000),
        used_tokens_this_period=row.get("used_tokens_this_period", 0),
        billing_period_start=dt.date.fromisoformat(row.get("billing_period_start")),
    )


def estimate_tokens(text: str) -> int:
    """简单估算 token 数：按字符数 / 1.5 向上取整。"""
    chars = len(text)
    return max(1, math.ceil(chars / 1.5))


def refresh_billing_period(sb: Client, user: AuthedUser) -> AuthedUser:
    """如果已经跨月，则重置本期用量。"""
    today = dt.date.today()
    if (today.year, today.month) != (user.billing_period_start.year, user.billing_period_start.month):
        res = (
            sb.table("users")
            .update(
                {
                    "used_tokens_this_period": 0,
                    "billing_period_start": today.isoformat(),
                }
            )
            .eq("id", user.user_row_id)
            .execute()
        )
        row = res.data[0]
        user.used_tokens_this_period = 0
        user.billing_period_start = today
        user.monthly_quota_tokens = row.get("monthly_quota_tokens", user.monthly_quota_tokens)
    return user


@app.post("/translate", response_model=TranslateResponse)
async def translate(
    body: TranslateRequest,
    user: AuthedUser = Depends(get_current_user),
):
    sb = get_supabase_client()
    user = refresh_billing_period(sb, user)

    est_tokens = estimate_tokens(body.text)
    remaining = user.monthly_quota_tokens - user.used_tokens_this_period

    if est_tokens > remaining:
        raise HTTPException(
            status_code=402,
            detail=f"本月额度不足，剩余 {remaining} tokens，需要 {est_tokens} tokens",
        )

    # 调用智谱翻译（复用现有同步函数）
    ok, result, _elapsed = translate_text_sync(body.text, body.target_lang)
    if not ok:
        raise HTTPException(status_code=500, detail=f"翻译失败: {result}")

    # 记录 usage_logs & 更新 users 表的用量
    new_used = user.used_tokens_this_period + est_tokens

    sb.table("usage_logs").insert(
        {
            "user_id": user.user_row_id,
            "model": "glm-4.5",
            "input_chars": len(body.text),
            "estimated_tokens": est_tokens,
            "cost_in_cents": 0,
            "original_text": body.text,
            "translated_text": result,
        }
    ).execute()

    # 更新按月汇总表 user_monthly_usage
    period_start = dt.date(user.billing_period_start.year, user.billing_period_start.month, 1)
    existing = (
        sb.table("user_monthly_usage")
        .select("*")
        .eq("user_id", user.user_row_id)
        .eq("period_start", period_start.isoformat())
        .execute()
    ).data

    if existing:
        row = existing[0]
        sb.table("user_monthly_usage").update(
            {
                "total_tokens": row.get("total_tokens", 0) + est_tokens,
                "total_requests": row.get("total_requests", 0) + 1,
                "updated_at": dt.datetime.utcnow().isoformat(),
            }
        ).eq("id", row["id"]).execute()
    else:
        sb.table("user_monthly_usage").insert(
            {
                "user_id": user.user_row_id,
                "period_start": period_start.isoformat(),
                "total_tokens": est_tokens,
                "total_requests": 1,
            }
        ).execute()

    sb.table("users").update(
        {"used_tokens_this_period": new_used}
    ).eq("id", user.user_row_id).execute()

    return TranslateResponse(
        translated_text=result,
        estimated_tokens=est_tokens,
        remaining_tokens=user.monthly_quota_tokens - new_used,
    )


@app.get("/me/usage")
async def get_usage(user: AuthedUser = Depends(get_current_user)):
    """供前端展示当前配额和已用量。"""
    return {
        "monthly_quota_tokens": user.monthly_quota_tokens,
        "used_tokens_this_period": user.used_tokens_this_period,
        "billing_period_start": user.billing_period_start.isoformat(),
        "remaining_tokens": user.monthly_quota_tokens - user.used_tokens_this_period,
    }


if __name__ == "__main__":
    import uvicorn

    # 直接通过 python main.py 启动 uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )



