# Digital-Economy-Literature-Review-Intelligent-Agent 架构说明

## 1. 产品形态

仓库现在按两个明确入口组织：

- 主产品入口：`FastAPI + React`
  - 面向最终演示、答辩和产品呈现
  - 负责统一的检索、生成、证据展示和导出体验
- 内部运维入口：`Streamlit`
  - 面向语料入库、索引维护、结果检查和调试

这样的拆分避免了多个“平行 demo”互相竞争主入口。

## 2. 系统分层

### 表现层

- `web/`
  - React + Vite 前端
  - 负责查询输入、筛选项、结果展示、运行摘要、导出
- `backend.py`
  - FastAPI API
  - 负责请求校验、运行时配置暴露、索引状态暴露、调用 RAG 主链路
- `app_agent_ui.py`
  - Streamlit 运维台
  - 负责 PDF 上传、增量解析、索引更新、证据检查、评估与导出

### 业务层

- `src/rag_chain.py`
  - 主 RAG 编排
  - 执行本地检索、arXiv 检索、证据合并、提示词生成、引用修复
- `src/metadata_taxonomy.py`
  - 元数据分类、标准化、标签和过滤逻辑
- `src/evaluation.py`
  - 质量评估逻辑

### 数据层

- `src/pdf_pipeline.py`
  - PDF 解析、文档切块、chunk 序号维护
- `src/indexing.py`
  - FAISS 建库、加载、增量 upsert
- `data/raw_pdfs/`
  - 原始 PDF 输入
- `data/processed/`
  - 处理后的 chunk 数据
- `data/index/`
  - 向量索引

## 3. 主请求链路

1. 用户在 Web 端输入研究问题和过滤条件
2. `backend.py` 校验参数并调用 `generate_review`
3. `rag_chain.py` 根据 `source_mode` 执行：
   - 本地 FAISS 检索
   - arXiv 在线摘要检索
   - 元数据过滤与证据合并
4. LLM 基于证据生成结构化综述
5. 如果引用不合法，则执行一次 citation repair
6. API 返回：
   - review 文本
   - metadata
   - sources

## 4. 当前仓库约束

- 年份过滤范围：`2018-2025`
- 主要检索源：
  - 本地 PDF chunk
  - arXiv abstract
- 当前输出语言默认由 `rag_chain.py` 控制为英文综述

## 5. 为什么这样整理

本次整理重点不是再加一层 demo，而是让仓库满足以下判断标准：

- 主入口唯一，产品叙事清晰
- 文档不重复
- 演示入口和运维入口角色分离
- 前后端暴露能力一致，不再出现“后端支持但前端没有”的割裂
