"""
翻译服务 - 处理翻译相关的业务逻辑
"""

import datetime as dt
from typing import Tuple

try:
    from api._shared import (
        get_supabase_client,
        translate_text_sync,
        estimate_tokens,
        refresh_billing_period,
        AuthedUser,
    )
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from api._shared import (
        get_supabase_client,
        translate_text_sync,
        estimate_tokens,
        refresh_billing_period,
        AuthedUser,
    )


class TranslateService:
    """翻译服务类"""
    
    @staticmethod
    async def translate_text(
        user: AuthedUser,
        text: str,
        target_lang: str = "英文"
    ) -> Tuple[str, int, int]:
        """
        执行翻译并更新用量
        
        Returns:
            (translated_text, estimated_tokens, remaining_tokens)
        """
        sb = get_supabase_client()
        user = refresh_billing_period(sb, user)

        est_tokens = estimate_tokens(text)
        remaining = user.monthly_quota_tokens - user.used_tokens_this_period

        if est_tokens > remaining:
            raise ValueError(f"本月额度不足，剩余 {remaining} tokens，需要 {est_tokens} tokens")

        # 调用智谱翻译
        ok, result, _elapsed = translate_text_sync(text, target_lang)
        if not ok:
            raise RuntimeError(f"翻译失败: {result}")

        # 记录 usage_logs & 更新 users 表的用量
        new_used = user.used_tokens_this_period + est_tokens

        # 记录使用日志
        sb.table("usage_logs").insert(
            {
                "user_id": user.user_row_id,
                "model": "glm-4.5",
                "input_chars": len(text),
                "estimated_tokens": est_tokens,
                "cost_in_cents": 0,
                "original_text": text,
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

        # 更新用户用量
        sb.table("users").update(
            {"used_tokens_this_period": new_used}
        ).eq("id", user.user_row_id).execute()

        remaining_tokens = user.monthly_quota_tokens - new_used
        return result, est_tokens, remaining_tokens

