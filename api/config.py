"""
配置模块 - 优先从环境变量读取，否则使用默认值
"""

import os

# Supabase 配置（优先使用环境变量，否则使用默认值）
SUPABASE_URL = os.getenv("SUPABASE_URL") or "https://bdxgeqvzvcnlsldlvnum.supabase.co"
SUPABASE_SERVICE_KEY = (
    os.getenv("SUPABASE_SERVICE_KEY") 
    or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJkeGdlcXZ6dmNubHNsZGx2bnVtIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NjQzNjQzMywiZXhwIjoyMDgyMDEyNDMzfQ.UeVqCEXnR9nprR32vscDjBY_dAgY9nw4gtmjgSR8Epk"
)

# 智谱 AI 配置（优先使用环境变量，否则使用默认值）
ZHIPU_API_KEY = os.getenv("ZHIPU_API_KEY") or "276b6402f853cb58c5360dcf3a1dc172.rcxQP9TaFbxM39Yi"

# Supabase Anon Key（前端使用，如果需要的话）
SUPABASE_ANON_KEY = (
    os.getenv("SUPABASE_ANON_KEY") 
    or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImJkeGdlcXZ6dmNubHNsZGx2bnVtIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjY0MzY0MzMsImV4cCI6MjA4MjAxMjQzM30.AetYNUKsYfye6VB3a8_zAQCaYPohvv0IyniMsORt3xM"
)

