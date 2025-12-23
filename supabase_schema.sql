-- Supabase 计费/翻译系统表结构设计

-- 1) 扩展现有 public.users 表，增加 auth_user_id（关联 auth.users）、计费相关字段
ALTER TABLE public.users
ADD COLUMN IF NOT EXISTS auth_user_id uuid UNIQUE,
ADD COLUMN IF NOT EXISTS monthly_quota_tokens bigint DEFAULT 50000, -- 每月配额，示例：5 万 token
ADD COLUMN IF NOT EXISTS used_tokens_this_period bigint DEFAULT 0,  -- 本计费周期已用 token
ADD COLUMN IF NOT EXISTS billing_period_start date DEFAULT CURRENT_DATE;

COMMENT ON COLUMN public.users.auth_user_id IS '关联 auth.users.id，用于从 Supabase Auth 映射到业务用户';
COMMENT ON COLUMN public.users.monthly_quota_tokens IS '每月可用 token 配额';
COMMENT ON COLUMN public.users.used_tokens_this_period IS '当前计费周期内已消耗的 token 数';
COMMENT ON COLUMN public.users.billing_period_start IS '当前计费周期开始日期，用于按月重置';

-- 2) usage_logs：记录每次翻译调用的用量
CREATE TABLE IF NOT EXISTS public.usage_logs (
    id bigserial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    model text NOT NULL DEFAULT 'glm-4.5',
    input_chars integer NOT NULL,
    estimated_tokens integer NOT NULL,
    cost_in_cents integer NOT NULL DEFAULT 0, -- 如需真实计费可以填这里
    original_text text,                        -- 原文
    translated_text text,                      -- 译文
    created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.usage_logs IS '逐次翻译调用的用量日志';

-- 2.1 user_monthly_usage：每个用户每个月的用量汇总
CREATE TABLE IF NOT EXISTS public.user_monthly_usage (
    id bigserial PRIMARY KEY,
    user_id bigint NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    period_start date NOT NULL,                -- 计费周期开始日期（一般为当月第一天）
    total_tokens bigint NOT NULL DEFAULT 0,
    total_requests integer NOT NULL DEFAULT 0,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, period_start)
);

COMMENT ON TABLE public.user_monthly_usage IS '每个用户每个月的用量汇总';

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.usage_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.user_monthly_usage ENABLE ROW LEVEL SECURITY;

-- 如已存在旧策略，可手动先执行：
-- DROP POLICY IF EXISTS "Users can view own profile" ON public.users;
-- DROP POLICY IF EXISTS "Users can view own usage logs" ON public.usage_logs;

-- 只允许用户访问自己的 users 行（仅 SELECT）
CREATE POLICY "Users can view own profile"
ON public.users
FOR SELECT
USING (auth.uid() = auth_user_id);

-- 只允许用户查看自己的 usage_logs（仅 SELECT）
CREATE POLICY "Users can view own usage logs"
ON public.usage_logs
FOR SELECT
USING (
    EXISTS (
        SELECT 1 FROM public.users u
        WHERE u.id = usage_logs.user_id
          AND u.auth_user_id = auth.uid()
    )
);

-- 只允许用户查看自己的每月用量（仅 SELECT）
CREATE POLICY "Users can view own monthly usage"
ON public.user_monthly_usage
FOR SELECT
USING (
    EXISTS (
        SELECT 1 FROM public.users u
        WHERE u.id = user_monthly_usage.user_id
          AND u.auth_user_id = auth.uid()
    )
);


