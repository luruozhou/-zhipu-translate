"""
用户服务 - 处理用户相关的业务逻辑
"""

try:
    from api._shared import AuthedUser
except ImportError:
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from api._shared import AuthedUser


class UserService:
    """用户服务类"""
    
    @staticmethod
    def get_usage_info(user: AuthedUser) -> dict:
        """
        获取用户用量信息
        
        Returns:
            {
                "monthly_quota_tokens": int,
                "used_tokens_this_period": int,
                "billing_period_start": str,
                "remaining_tokens": int
            }
        """
        return {
            "monthly_quota_tokens": user.monthly_quota_tokens,
            "used_tokens_this_period": user.used_tokens_this_period,
            "billing_period_start": user.billing_period_start.isoformat(),
            "remaining_tokens": user.monthly_quota_tokens - user.used_tokens_this_period,
        }

