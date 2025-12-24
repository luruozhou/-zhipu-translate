// backend/server.js
// 使用 Express 重写原来的 FastAPI 后端，保持接口兼容：
// - POST /translate
// - GET  /me/usage
// - GET  /api/packages
//
// 依赖：
//   - config.json 中需要包含：
//       SUPABASE_URL
//       SUPABASE_KEY      (service_role key)
//       ZHIPU_API_KEY

const path = require('path');
const fs = require('fs');
const express = require('express');
const cors = require('cors');
const axios = require('axios');
const { createClient } = require('@supabase/supabase-js');

// ---------- 加载配置 ----------
const ROOT_DIR = path.resolve(__dirname, '..');

function loadConfig() {
  const configPath = path.join(ROOT_DIR, 'config.json');
  if (!fs.existsSync(configPath)) {
    throw new Error('缺少 config.json，用于读取 SUPABASE_URL / SUPABASE_KEY / ZHIPU_API_KEY');
  }
  const raw = fs.readFileSync(configPath, 'utf-8');
  return JSON.parse(raw);
}

const cfg = loadConfig();
const SUPABASE_URL = process.env.SUPABASE_URL || cfg.SUPABASE_URL;
const SUPABASE_SERVICE_KEY = process.env.SUPABASE_SERVICE_KEY || cfg.SUPABASE_KEY;
const ZHIPU_API_KEY = process.env.ZHIPU_API_KEY || cfg.ZHIPU_API_KEY;

if (!SUPABASE_URL || !SUPABASE_SERVICE_KEY) {
  throw new Error('缺少 SUPABASE_URL / SUPABASE_SERVICE_KEY');
}
if (!ZHIPU_API_KEY) {
  throw new Error('缺少 ZHIPU_API_KEY');
}

// ---------- Supabase 客户端 ----------
function getSupabaseClient() {
  return createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY);
}

// ---------- 翻译调用 ----------
async function translateTextSync(text, targetLang) {
  const start = Date.now();
  try {
    const resp = await axios.post(
      'https://open.bigmodel.cn/api/paas/v4/chat/completions',
      {
        model: 'GLM-4-Flash-250414',
        messages: [
          {
            role: 'user',
            content:
              '你是一个专业的翻译助手。' +
              `请将我给你的文本翻译成目标语言：${targetLang}。` +
              "目标语言的描述可能是自然语言（例如'简体中文''英语'），" +
              '也可能是语言代码（例如 zh、en、ja、fr 等），' +
              '请根据这个描述自行理解目标语言并进行翻译。' +
              '只输出翻译后的文本本身，不要任何解释或前后缀。',
          },
          {
            role: 'user',
            content: text,
          },
        ],
        thinking: { type: 'disabled' },
        stream: false,
        max_tokens: 2048,
        temperature: 0.3,
      },
      {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${ZHIPU_API_KEY}`,
        },
        timeout: 20000,
      }
    );

    const result = resp.data.choices?.[0]?.message?.content || '';
    const elapsed = (Date.now() - start) / 1000;
    return [true, result, elapsed];
  } catch (e) {
    const elapsed = (Date.now() - start) / 1000;
    return [false, e.message || String(e), elapsed];
  }
}

// ---------- 工具函数 ----------
function estimateTokens(text) {
  const chars = text.length;
  return Math.max(1, Math.ceil(chars / 1.5));
}

// ---------- 鉴权中间件 ----------
async function authMiddleware(req, res, next) {
  const authHeader = req.headers['authorization'] || '';
  if (!authHeader.toLowerCase().startsWith('bearer ')) {
    return res.status(401).json({ detail: '缺少 Authorization Bearer token' });
  }

  const accessToken = authHeader.split(' ')[1];
  const sb = getSupabaseClient();

  try {
    // 调用 Supabase Auth API 获取用户信息
    const resp = await axios.get(`${SUPABASE_URL}/auth/v1/user`, {
      headers: {
        Authorization: `Bearer ${accessToken}`,
        apikey: SUPABASE_SERVICE_KEY,
      },
      timeout: 10000,
    });

    const authUser = resp.data;
    const authUserId = authUser.id;

    // 映射到 public.users（如果不存在则自动创建）
    const { data, error } = await sb
      .from('users')
      .select('*')
      .eq('auth_user_id', authUserId);

    if (error) {
      console.error('查询 users 表出错:', error);
      return res.status(500).json({ detail: '查询用户信息失败' });
    }

    let row;
    if (data && data.length > 0) {
      row = data[0];
    } else {
      const profile = {
        auth_user_id: authUserId,
        name: authUser.user_metadata?.full_name || authUser.email,
      };
      const insertRes = await sb.from('users').insert(profile).select().single();
      if (insertRes.error) {
        console.error('创建 users 表记录失败:', insertRes.error);
        return res.status(500).json({ detail: '创建用户记录失败' });
      }
      row = insertRes.data;
    }

    req.currentUser = {
      auth_user_id: authUserId,
      user_row_id: row.id,
      monthly_quota_tokens: row.monthly_quota_tokens ?? 50000,
      used_tokens_this_period: row.used_tokens_this_period ?? 0,
      billing_period_start: row.billing_period_start,
    };

    next();
  } catch (e) {
    console.error('验证 Supabase 会话失败:', e.response?.data || e.message || e);
    return res.status(401).json({ detail: '无效的 Supabase 会话' });
  }
}

// ---------- 计费周期刷新 ----------
async function refreshBillingPeriod(sb, user) {
  const today = new Date();
  const current = new Date(user.billing_period_start);
  if (
    !user.billing_period_start ||
    today.getFullYear() !== current.getFullYear() ||
    today.getMonth() !== current.getMonth()
  ) {
    const { data, error } = await sb
      .from('users')
      .update({
        used_tokens_this_period: 0,
        billing_period_start: today.toISOString().slice(0, 10),
      })
      .eq('id', user.user_row_id)
      .select()
      .single();

    if (!error && data) {
      user.used_tokens_this_period = 0;
      user.billing_period_start = data.billing_period_start;
      user.monthly_quota_tokens = data.monthly_quota_tokens ?? user.monthly_quota_tokens;
    }
  }
  return user;
}

// ---------- Express App ----------
const app = express();

app.use(
  cors({
    origin: ['http://localhost:3000', 'http://127.0.0.1:3000', 'http://localhost:5173'],
    credentials: true,
  })
);
app.use(express.json({ limit: '1mb' }));

// POST /translate
app.post('/translate', authMiddleware, async (req, res) => {
  const { text, target_lang = '英文' } = req.body || {};
  if (!text || typeof text !== 'string') {
    return res.status(400).json({ detail: 'text 必须是非空字符串' });
  }

  const sb = getSupabaseClient();
  let user = req.currentUser;
  user = await refreshBillingPeriod(sb, user);

  const estTokens = estimateTokens(text);
  const remaining = user.monthly_quota_tokens - user.used_tokens_this_period;

  if (estTokens > remaining) {
    return res.status(402).json({
      detail: `本月额度不足，剩余 ${remaining} tokens，需要 ${estTokens} tokens`,
    });
  }

  const [ok, result, _elapsed] = await translateTextSync(text, target_lang);
  if (!ok) {
    return res.status(500).json({ detail: `翻译失败: ${result}` });
  }

  const newUsed = user.used_tokens_this_period + estTokens;

  // 记录 usage_logs
  await sb.from('usage_logs').insert({
    user_id: user.user_row_id,
    model: 'glm-4.5',
    input_chars: text.length,
    estimated_tokens: estTokens,
    cost_in_cents: 0,
    original_text: text,
    translated_text: result,
  });

  // 更新 user_monthly_usage
  const billingStart = new Date(user.billing_period_start || new Date());
  const periodStart = new Date(billingStart.getFullYear(), billingStart.getMonth(), 1);
  const periodStartStr = periodStart.toISOString().slice(0, 10);

  const existing = await sb
    .from('user_monthly_usage')
    .select('*')
    .eq('user_id', user.user_row_id)
    .eq('period_start', periodStartStr)
    .maybeSingle();

  if (existing.data) {
    const row = existing.data;
    await sb
      .from('user_monthly_usage')
      .update({
        total_tokens: (row.total_tokens || 0) + estTokens,
        total_requests: (row.total_requests || 0) + 1,
        updated_at: new Date().toISOString(),
      })
      .eq('id', row.id);
  } else {
    await sb.from('user_monthly_usage').insert({
      user_id: user.user_row_id,
      period_start: periodStartStr,
      total_tokens: estTokens,
      total_requests: 1,
    });
  }

  // 更新 users 用量
  await sb
    .from('users')
    .update({ used_tokens_this_period: newUsed })
    .eq('id', user.user_row_id);

  return res.json({
    translated_text: result,
    estimated_tokens: estTokens,
    remaining_tokens: user.monthly_quota_tokens - newUsed,
  });
});

// GET /me/usage
app.get('/me/usage', authMiddleware, async (req, res) => {
  const user = req.currentUser;
  return res.json({
    monthly_quota_tokens: user.monthly_quota_tokens,
    used_tokens_this_period: user.used_tokens_this_period,
    billing_period_start: user.billing_period_start,
    remaining_tokens: user.monthly_quota_tokens - user.used_tokens_this_period,
  });
});

// GET /api/packages  —— 保留套餐接口，后面可接 YunGouOS 支付
app.get('/api/packages', (_req, res) => {
  return res.json([
    {
      id: 'basic',
      name: '基础套餐',
      tokens_amount: 100000,
      price_cents: 9900,
      description: '适合轻度使用',
    },
    {
      id: 'standard',
      name: '标准套餐',
      tokens_amount: 500000,
      price_cents: 39900,
      description: '适合日常使用',
    },
    {
      id: 'premium',
      name: '高级套餐',
      tokens_amount: 2000000,
      price_cents: 129900,
      description: '适合重度使用',
    },
  ]);
});

// 健康检查
app.get('/healthz', (_req, res) => {
  res.json({ status: 'ok' });
});

// ---------- 启动服务 ----------
const PORT = process.env.PORT || 8000;
app.listen(PORT, () => {
  console.log(`Express backend listening on http://localhost:${PORT}`);
});


