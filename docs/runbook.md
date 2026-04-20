# Digital-Economy-Literature-Review-Intelligent-Agent 运行手册

## 1. 环境要求

- Python 3.10+
- Node.js 18+
- Windows / macOS / Linux 均可

## 2. 安装

```bash
pip install -r requirements.txt
cd web && npm install
```

## 3. 环境变量

```bash
copy .env.example .env
```

关键变量：

- `LLM_PROVIDER`
- `LLM_MODEL`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `EMBEDDING_MODEL`
- `RETRIEVE_TOP_K`
- `ARXIV_MAX_RESULTS`

## 4. 数据准备

把论文 PDF 放入：

```text
data/raw_pdfs/
```

然后运行：

```bash
python scripts/build_corpus.py
python scripts/build_index.py --batch-size 256
```

小样本调试：

```bash
python scripts/build_index.py --max-chunks 2000 --batch-size 256
```

## 5. 启动方式

### 主产品

终端 1：

```bash
python -m uvicorn backend:app --reload --host 0.0.0.0 --port 8000
```

终端 2：

```bash
cd web
npm run dev
```

访问地址：

- Web：`http://localhost:5173`
- API Docs：`http://localhost:8000/docs`

### 一键启动

```bash
run-all.bat
```

### 运维工作台

```bash
streamlit run app_agent_ui.py
```

## 6. 常见操作

### 生成一次综述

```bash
python scripts/generate_review.py --query "Platform economy impacts on labor market" --source-mode local_plus_arxiv
```

### 评估结果

```bash
python scripts/evaluate_output.py --input outputs/review_YYYYMMDD_HHMMSS.json
```

## 7. 故障排查

### 索引不存在

先后执行：

```bash
python scripts/build_corpus.py
python scripts/build_index.py
```

### PDF AES 报错

如果出现 `cryptography>=3.1 is required for AES algorithm`：

```bash
pip install -r requirements.txt
```

同时确认安装依赖和运行脚本使用的是同一个 Python 解释器。

### Web 无法请求 API

- 确认后端运行在 `8000`
- 如需自定义前端 API 地址，在 `web/.env.local` 设置：

```env
VITE_API_URL=http://localhost:8000
```

### 无结果或结果太少

- 检查索引是否存在
- 放宽 `subfields` / `journal_categories` / `journal_codes`
- 放宽年份范围
- 提高 `top_k`
- 切换到 `local_plus_arxiv`
