"""
共享的工具函数和配置
"""

import os
import json
import math
import datetime as dt
from pathlib import Path
from typing import Tuple

import httpx
from fastapi import HTTPException
from supabase import create_client, Client
from zai import ZhipuAiClient


def load_config():
    """从项目根目录的 config.json 读取配置。"""
    # 获取项目根目录（api 目录的上一级）
    current_file = Path(__file__).resolve()
    root_dir = current_file.parent.parent
    config_path = root_dir / "config.json"
    
    if not config_path.exists():
        raise RuntimeError(f"缺少 config.json 文件，请在项目根目录创建：{config_path}")
    
    with config_path.open("r", encoding="utf-8") as f:
        config = json.load(f)
    
    return config


def load_supabase_config():
    """从 config.json 读取 Supabase 配置。"""
    config = load_config()
    supabase_url = config.get("SUPABASE_URL")
    supabase_service_key = config.get("SUPABASE_KEY") or config.get("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_service_key:
        raise RuntimeError("config.json 中缺少 SUPABASE_URL / SUPABASE_KEY，请检查配置")

    return supabase_url, supabase_service_key


SUPABASE_URL, SUPABASE_SERVICE_KEY = load_supabase_config()


def get_zhipu_client() -> ZhipuAiClient:
    """从 config.json 读取 ZHIPU_API_KEY，并创建 ZhipuAiClient。"""
    config = load_config()
    api_key = config.get("ZHIPU_API_KEY")
    if not api_key:
        raise RuntimeError("config.json 中缺少 ZHIPU_API_KEY，请检查配置")

    return ZhipuAiClient(api_key=api_key)


def translate_text_sync(text: str, target_lang: str) -> Tuple[bool, str, float]:
    """
    同步版本的翻译函数。
    返回: (是否成功, 错误信息或结果, 耗时)
    """
    import time
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


class AuthedUser:
    def __init__(self, auth_user_id: str, user_row_id: int, monthly_quota_tokens: int,
                 used_tokens_this_period: int, billing_period_start: dt.date):
        self.auth_user_id = auth_user_id
        self.user_row_id = user_row_id
        self.monthly_quota_tokens = monthly_quota_tokens
        self.used_tokens_this_period = used_tokens_this_period
        self.billing_period_start = billing_period_start


async def get_current_user(authorization: str = None) -> AuthedUser:
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

