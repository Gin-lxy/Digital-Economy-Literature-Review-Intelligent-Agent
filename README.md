# Digital-Economy-Literature-Review-Intelligent-Agent

`Digital-Economy-Literature-Review-Intelligent-Agent` 是一个面向文献综述场景的成熟型 agent 产品仓库，而不是课程作业式 demo 堆叠。主产品入口为 `FastAPI + React` Web 应用，负责检索编排、元数据过滤、生成、证据展示和导出；`Streamlit` 保留为内部运维工作台，用于 PDF 增量入库、索引维护与质量检查。

## 产品定位

- 面向数字经济/管理学文献综述的检索增强生成 agent
- 支持本地 PDF 语料与 arXiv 在线摘要的混合证据检索
- 支持按 `subfield`、`journal_category`、`journal_code`、`publication year` 过滤
- 输出带来源引用的综述草稿，并支持 Markdown / PDF / JSON 导出
- 保留评估与消融实验脚本，方便论文交付和后续迭代

## 主入口

- Web 产品：`backend.py` + `web/`
- 内部运维台：`app_agent_ui.py`
- 一键启动：`run-all.bat`

## 快速启动

1. 安装依赖

```bash
pip install -r requirements.txt
cd web && npm install
```

2. 配置环境变量

```bash
copy .env.example .env
```

按你的模型服务填写 `.env`，至少需要配置：

- `LLM_PROVIDER`
- `LLM_MODEL`
- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`（如需）

3. 准备语料并构建索引

```bash
python scripts/build_corpus.py
python scripts/build_index.py --batch-size 256
```

如果只做小样本验证：

```bash
python scripts/build_index.py --max-chunks 2000 --batch-size 256
```

4. 启动主产品

```bash
python -m uvicorn backend:app --reload --host 0.0.0.0 --port 8000
```

新建终端，启动前端：

```bash
cd web && npm run dev
```

5. 可选：启动内部运维工作台

```bash
streamlit run app_agent_ui.py
```

## 核心能力

- 混合证据模式：`local_only`、`arxiv_only`、`local_plus_arxiv`
- 本地 PDF 解析、切块、FAISS 建库与增量 upsert
- 元数据自动补全与检索期过滤
- 文献综述生成与引用修复
- 证据列表、运行历史与结构化导出
- 评估脚本与消融实验脚本

## 目录结构

```text
rag/
  backend.py                # FastAPI 主 API
  app_agent_ui.py           # Streamlit 运维工作台
  run-all.bat               # 主产品一键启动
  requirements.txt
  data/
  dify/
  docs/
    architecture.md         # 产品与系统架构
    runbook.md              # 运行、构建、排障
  scripts/
    build_corpus.py
    build_index.py
    generate_review.py
    evaluate_output.py
    ablation_level.py
  src/
    config.py
    pdf_pipeline.py
    indexing.py
    metadata_taxonomy.py
    rag_chain.py
    evaluation.py
    arxiv_retriever.py
  web/
    src/
```

## 常用命令

生成一段综述：

```bash
python scripts/generate_review.py --query "Platform economy impacts on labor market" --source-mode local_plus_arxiv --arxiv-max-results 3
```

带元数据过滤：

```bash
python scripts/generate_review.py --query "Digital platform governance" --source-mode local_only --subfields platform_economy,digital_governance_and_ai --journal-categories information_systems,organization_and_strategy
```

带期刊代码和年份过滤：

```bash
python scripts/generate_review.py --query "ESG disclosure impact" --source-mode local_plus_arxiv --journal-codes JBE,JMIS,ARXIV --year-from 2020 --year-to 2025
```

评估单次输出：

```bash
python scripts/evaluate_output.py --input outputs/review_YYYYMMDD_HHMMSS.json
```

## 文档

- [架构说明](docs/architecture.md)
- [运行手册](docs/runbook.md)
- [Dify 部署说明](dify/DEPLOYMENT_GUIDE.md)
