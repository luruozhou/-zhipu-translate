# 智谱翻译系统

基于 Vercel 部署的前后端一体化翻译应用，使用 Supabase 进行用户认证和数据存储，智谱 AI 提供翻译服务。

## 项目结构

```
zhipu-translate/
├── api/                    # Vercel Serverless Functions
│   ├── translate.js       # 翻译接口
│   ├── me/
│   │   └── usage.js      # 用户用量查询接口
│   ├── packages.js        # 套餐列表接口
│   └── healthz.js         # 健康检查接口
├── src/                   # 前端源代码
│   ├── App.tsx           # 主应用组件
│   ├── main.tsx          # 入口文件
│   └── lib/
│       └── supabaseClient.ts  # Supabase 客户端
├── index.html            # HTML 入口
├── vite.config.mts       # Vite 配置
├── vercel.json           # Vercel 部署配置
└── package.json          # 项目依赖
```

## 环境变量配置

### 本地开发

1. 复制 `.env.example` 文件为 `.env`：
```bash
cp .env.example .env
```

2. 编辑 `.env` 文件，填入你的配置（参考 `.env.example`）：
```env
# Supabase 配置
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key
SUPABASE_ANON_KEY=your_anon_key

# 智谱 AI 配置
ZHIPU_API_KEY=your_zhipu_api_key

# 前端环境变量（Vite 需要 VITE_ 前缀）
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your_anon_key
```

**注意**：`.env` 文件包含敏感信息，已被 `.gitignore` 忽略，不会提交到代码仓库。

### Vercel 部署

在 Vercel 项目设置中配置以下环境变量：

#### 必需的环境变量

- `SUPABASE_URL`: Supabase 项目 URL
- `SUPABASE_SERVICE_KEY`: Supabase Service Role Key（用于后端 API）
- `ZHIPU_API_KEY`: 智谱 AI API Key

#### 前端环境变量（可选）

- `VITE_SUPABASE_URL`: Supabase 项目 URL（前端使用）
- `VITE_SUPABASE_ANON_KEY`: Supabase Anon Key（前端使用）

## 本地开发

### 前端开发

1. 安装依赖：
```bash
npm install
```

2. 确保 `config.json` 文件已配置（参考上面的"环境变量配置"部分）

3. 启动前端开发服务器：
```bash
npm run dev
```

前端服务将在 `http://localhost:3000` 启动

### 后端开发

1. 安装 Python 依赖：
```bash
pip install -r requirements.txt
```

2. 确保 `config.json` 文件已配置（参考上面的"环境变量配置"部分）

3. 启动后端服务：
```bash
# 方式一：直接运行 Python 文件（推荐）
python api/app.py

# 方式二：使用 uvicorn 命令启动
uvicorn api.app:app --reload --host 0.0.0.0 --port 8000

# 方式三：使用 Python 模块方式启动
python -m uvicorn api.app:app --reload --host 0.0.0.0 --port 8000
```

后端服务将在 `http://localhost:8000` 启动

**API 文档**：启动后端后，可以访问 `http://localhost:8000/docs` 查看 Swagger API 文档

### 前后端联调

- 前端：`http://localhost:3000`
- 后端：`http://localhost:8000`
- Vite 已配置代理，前端的 `/api/*` 请求会自动代理到 `http://localhost:8000`

**注意**：确保后端服务先启动，前端才能正常调用 API

## 部署到 Vercel

### 方法一：通过 Vercel CLI

1. 安装 Vercel CLI：
```bash
npm i -g vercel
```

2. 登录并部署：
```bash
vercel login
vercel
```

3. 配置环境变量：
```bash
vercel env add SUPABASE_URL
vercel env add SUPABASE_SERVICE_KEY
vercel env add ZHIPU_API_KEY
```

### 方法二：通过 GitHub 集成

1. 将代码推送到 GitHub 仓库
2. 在 [Vercel Dashboard](https://vercel.com/dashboard) 中导入项目
3. 在项目设置中配置环境变量：
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`
   - `ZHIPU_API_KEY`
4. 点击部署

## API 接口

### POST /api/translate
翻译文本

**请求头：**
```
Authorization: Bearer <supabase_jwt_token>
Content-Type: application/json
```

**请求体：**
```json
{
  "text": "要翻译的文本",
  "target_lang": "英文"
}
```

**响应：**
```json
{
  "translated_text": "翻译结果",
  "estimated_tokens": 100,
  "remaining_tokens": 49900
}
```

### GET /api/me/usage
获取当前用户用量信息

**请求头：**
```
Authorization: Bearer <supabase_jwt_token>
```

**响应：**
```json
{
  "monthly_quota_tokens": 50000,
  "used_tokens_this_period": 100,
  "billing_period_start": "2024-01-01",
  "remaining_tokens": 49900
}
```

### GET /api/packages
获取套餐列表

**响应：**
```json
[
  {
    "id": "basic",
    "name": "基础套餐",
    "tokens_amount": 100000,
    "price_cents": 9900,
    "description": "适合轻度使用"
  }
]
```

## 注意事项

1. **环境变量安全**：确保 `SUPABASE_SERVICE_KEY` 和 `ZHIPU_API_KEY` 等敏感信息只配置在 Vercel 环境变量中，不要提交到代码仓库。

2. **CORS 配置**：API 函数已配置 CORS，允许跨域请求。

3. **Supabase 配置**：确保 Supabase 项目已正确配置 Google OAuth，并设置了相应的数据库表结构。

4. **构建输出**：Vite 构建输出到 `dist` 目录，Vercel 会自动识别并部署。

## 技术栈

- **前端**：React 17 + TypeScript + Vite
- **后端**：FastAPI + Vercel Serverless Functions (Python)
- **数据库/认证**：Supabase
- **AI 服务**：智谱 AI (GLM-4-Flash)
- **部署**：Vercel

