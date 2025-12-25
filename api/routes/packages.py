"""
套餐相关路由
"""

from fastapi import APIRouter

router = APIRouter()


@router.get("/packages")
async def get_packages():
    """获取套餐列表。"""
    return [
        {
            "id": "basic",
            "name": "基础套餐",
            "tokens_amount": 100000,
            "price_cents": 9900,
            "description": "适合轻度使用",
        },
        {
            "id": "standard",
            "name": "标准套餐",
            "tokens_amount": 500000,
            "price_cents": 39900,
            "description": "适合日常使用",
        },
        {
            "id": "premium",
            "name": "高级套餐",
            "tokens_amount": 2000000,
            "price_cents": 129900,
            "description": "适合重度使用",
        },
    ]

