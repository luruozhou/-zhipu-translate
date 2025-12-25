"""
Vercel Serverless Function 入口点
将所有 /api/* 请求路由到统一的 FastAPI app
"""

from mangum import Mangum
from api.app import app

# Vercel Serverless Function 入口
handler = Mangum(app, lifespan="off")

