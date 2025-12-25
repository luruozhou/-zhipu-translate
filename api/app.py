"""
FastAPI 应用主文件 - 统一的 FastAPI app 实例
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 创建统一的 FastAPI app
app = FastAPI(title="Translation & Billing API")

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 导入路由
from api.routes import translate, user, packages, healthz

# 注册路由（需要 /api 前缀，因为 Vercel 转发后路径仍然包含 /api）
app.include_router(translate.router, prefix="/api", tags=["translate"])
app.include_router(user.router, prefix="/api", tags=["user"])
app.include_router(packages.router, prefix="/api", tags=["packages"])
app.include_router(healthz.router, prefix="/api", tags=["health"])


# 本地开发启动入口
# if __name__ == "__main__":
#     import uvicorn
#     uvicorn.run(
#         "api.app:app",
#         host="0.0.0.0",
#         port=8000,
#         reload=True,
#     )

