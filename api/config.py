"""
配置模块 - 从 .env 文件或环境变量读取配置
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件（如果存在）
# 从项目根目录查找 .env 文件
current_file = Path(__file__).resolve()
root_dir = current_file.parent.parent
env_path = root_dir / ".env"

if env_path.exists():
    load_dotenv(env_path)
else:
    # 如果项目根目录没有 .env，也尝试加载当前目录的 .env（兼容性）
    load_dotenv()

# Supabase 配置
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# 智谱 AI 配置
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY")

# Supabase Anon Key（前端使用，如果需要的话）
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")

# 验证必需的配置
if not SUPABASE_URL:
    raise RuntimeError("缺少 SUPABASE_URL，请在 .env 文件或环境变量中配置")

if not SUPABASE_SERVICE_KEY:
    raise RuntimeError("缺少 SUPABASE_SERVICE_KEY，请在 .env 文件或环境变量中配置")

if not ZHIPU_API_KEY:
    raise RuntimeError("缺少 ZHIPU_API_KEY，请在 .env 文件或环境变量中配置")

