# 卡车配件 AI 产品数据中心（MVP）

面向卡车配件出口外贸企业的「AI 产品数据库」演示系统：把零散、不全的产品与供应商数据整理成标准化的零件号映射库，并用它来**秒级响应客户询价**（图片 → 配件 → 价格）、**AI 入库供应商资料**、**量化与修复数据质量**、**生成平台上架文案**。

- 产品需求：[docs/PRD.md](docs/PRD.md)
- 系统设计与设计取舍（ADR）：[docs/DESIGN.md](docs/DESIGN.md)

> ⚠️ 所有产品、零件号、供应商均为**按真实格式虚构的演示数据**。

## 技术栈

Django 5.2 LTS · PostgreSQL 16 + pgvector + pg_trgm · django-q2 · HTMX + Tailwind + Chart.js（已放在 `static/vendor`，离线可用）· OpenAI 兼容接口（DeepSeek / Kimi / 豆包 / 通义…）· pandas / openpyxl / pdfplumber · rapidfuzz · reportlab

## 快速开始

### 方式一：本地开发（推荐演示时使用）

```bash
cp .env.example .env              # 默认 AI_MOCK=True，无需 Key
docker compose up -d db           # 只启动数据库（127.0.0.1:5440）
uv sync
uv run python manage.py migrate
uv run python manage.py seed_demo # 生成演示数据、向量、质量扫描、演示文件；创建 admin/admin123
uv run python manage.py runserver
```

本地开发时在 `.env` 里设置 `Q_SYNC=True`，上传的供应商文件会在请求内同步处理，无需单独启动 worker；
或者另开终端运行 `uv run python manage.py qcluster` 走异步。

### 方式二：全部 Docker

```bash
cp .env.example .env
docker compose up -d --build      # db + web(8010) + worker
docker compose exec web python manage.py migrate
docker compose exec web python manage.py seed_demo
```

打开 http://127.0.0.1:8010 。

## 接入真实大模型

编辑 `.env`，设置 `AI_MOCK=False` 并填写 Key。对话、视觉、向量可以分别使用不同厂商：

```ini
# 示例：阿里云百炼（一个 Key 同时提供对话、视觉、向量，已实测可用）
AI_MOCK=False
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=sk-...
LLM_MODEL=qwen-plus
VISION_MODEL=qwen-vl-max
EMBEDDING_MODEL=text-embedding-v4     # 必须支持 1024 维输出

# 也可以分别使用不同厂商，例如对话用 DeepSeek：
# LLM_BASE_URL=https://api.deepseek.com/v1
# LLM_MODEL=deepseek-chat
# VISION_BASE_URL / VISION_API_KEY、EMBEDDING_BASE_URL / EMBEDDING_API_KEY 单独指定
```

未配置 `VISION_MODEL` / `EMBEDDING_MODEL` 时对应能力自动退回 Mock。

百炼实测耗时（2026-09）：询价解析 3–6 秒、识图约 3.5 秒、列映射约 2.6 秒、报价邮件约 9 秒、上架文案约 15 秒；一次完整演示约 25 次调用、token 合计约 1.2 万。切换向量模型后执行
`python manage.py build_embeddings --all` 重建向量。所有调用记录在后台「AI 调用日志」，提示词可在「提示词模板」中新建版本调优。

## 演示脚本（约 8 分钟）

| # | 页面 | 操作 | 讲点 |
|---|---|---|---|
| 1 | 总览 | 看 SKU 数、平均完整度 ~76、数据缺口 | 这是数据的真实状况，也是询价慢的根源 |
| 2 | 询价工作台 | 点样例「邮件询价」→ 开始匹配 | 精确号 100 分、写错一位的号 → 模糊匹配、只有描述 → 语义推荐；成本/MOQ/交期/建议售价一屏看全 |
| 3 | 询价详情 | 为第 3 行选一个候选、改数量 → 生成英文报价邮件 → 报价单 PDF | 价格只来自系统计算，AI 只负责措辞并被自动核对 |
| 4 | 询价工作台 | 选演示照片 `customer_photo_brake_pad.png` | 识图读出标签号码 → 精确命中 |
| 5 | 供应商资料入库 | 选演示文件 `供应商报价_恒达制动.xlsx` | 中文表头、带标题行也能识别；批量通过 ≥95；新品一键建草稿 SKU；产品详情出现新报价与 Knorr Cross 号 |
| 6 | 数据质量 | 一键单位标准化 → 某个重复问题「合并重复」→ 产品页「AI 补全建议」 | 规则可扩展；AI 只补文字，不碰号码与价格 |
| 7 | 上架文案 | 为高完整度 SKU 生成 Alibaba 文案 | 标题字数校验、号码防编造校验、导出 Shopify CSV |
| 8 | 后台 | 提示词模板 / AI 调用日志 / 询价反馈 | 经验沉淀：数据越用越准；后续对接 RCA-match / Supply-match |

## 常用命令

```bash
uv run pytest                                  # 测试（需要 db 容器在运行）
uv run python manage.py seed_demo              # 重置演示数据
uv run python manage.py run_quality_scan       # 全量质量扫描
uv run python manage.py build_embeddings --all # 重建产品向量
```

## 目录

```
apps/core       仪表盘、号码归一化等公共工具
apps/catalog    产品主数据（Product / PartNumber / Fitment…）、演示数据生成
apps/suppliers  供应商、报价、定价
apps/ai         统一 AI 客户端、Mock、提示词、调用日志、向量
apps/inquiry    询价工作台、分层匹配引擎、报价邮件与 PDF
apps/ingest     供应商文件读取、列映射、审核入库
apps/quality    质量规则引擎、完整度评分、修复动作
apps/listing    平台文案生成、校验、导出
docs/           PRD 与系统设计
demo_data/      seed 生成的供应商 Excel/PDF、客户照片、询价样例
```
