# 企业级 RAG 系统全面测试方案

> 目标：逐项验证 7 大优化模块 + 基础流水线，确认达到企业级标准 (≥90/100)

---

## 测试准备

### 准备测试文档集

在 `backend/data/` 下创建以下测试文件：

```
backend/data/
├── policy_2026.md          # 政策制度类文档（测试类别权重）
├── tech_architecture.md    # 技术文档（测试标题层级切分）
├── meeting_notes.md        # 会议纪要（测试低权重类别）
├── employee.xlsx           # 员工信息表（测试Excel合并单元格）
├── code_sample.py          # Python代码（测试AST切分）
├── code_sample.js          # JS代码（测试tree-sitter多语言）
├── scan_report.pdf         # 扫描版PDF（测试OCR）
└── multimodal_slides.pdf   # 含图片PDF（测试图片三路召回）
```

### API 基础路径

```
Base URL: http://127.0.0.1:8000
Auth Header: 需要有效的 JWT Token（通过 /user/login 获取）
```

---

## 第一轮：数据层面测试（第二章标准）

### 测试 1.1：Markdown 标题层级切分

**测试目的**：验证 HeadingSplitter 按 `#` 标题切分并保留路径上下文

**测试步骤**：
```bash
# 1. 创建测试 markdown 文件
cat > backend/data/heading_test.md << 'EOF'
# 第一章 系统概述
本章介绍系统的基本架构和设计理念。系统采用微服务架构，支持水平扩展。

## 1.1 核心组件
核心组件包括 API 网关、消息队列、数据库集群。

### 1.1.1 API 网关
API 网关负责请求路由、限流、认证。

## 1.2 部署方案
支持 Docker Compose 和 Kubernetes 两种部署方式。

# 第二章 快速开始
按照以下步骤快速启动系统。
EOF

# 2. 通过 API 上传文件（或用 uv run python 直接测试切分器）
cd backend && uv run python -c "
from app.rag.text_spliter import HeadingSplitter
hs = HeadingSplitter(chunk_size=400)
with open('data/heading_test.md') as f:
    text = f.read()
chunks = hs.split_text(text)
print(f'总 chunk 数: {len(chunks)}')
for i, c in enumerate(chunks):
    print(f'--- Chunk {i} ---')
    print(c[:150])
    print()
"
```

**企业级验收标准**：

| 验证项 | 要求 | 通过 |
|--------|------|------|
| Chunk 数量 | ≥4（两个一级标题各一个，1.1和1.1.1各一个） | |
| 标题路径 | Chunk 1.1 包含 `第一章 系统概述 > 1.1 核心组件` | |
| 层级嵌套 | Chunk 1.1.1 包含 `第一章 > 1.1 > 1.1.1` 三级路径 | |
| 无内容丢失 | 所有原文内容在某个 chunk 中出现 | |

---

### 测试 1.2：Excel 合并单元格 + 多级表头

**测试目的**：验证合并单元格值正确填充、多级表头正确拼接

**测试步骤**：
```bash
cd backend && uv run python -c "
import openpyxl
wb = openpyxl.Workbook()
ws = wb.active
ws.title = '员工信息'
# 多级表头：行1=部门，行2=具体列名
ws.merge_cells('A1:B1')
ws['A1'] = '基本信息'
ws['C1'] = '薪资'
ws['A2'] = '姓名'
ws['B2'] = '职位'
ws['C2'] = '月薪'
# 数据行
ws['A3'] = '张三'
ws['B3'] = '工程师'
ws['C3'] = 15000
ws['A4'] = '李四'
ws['B4'] = '经理'
ws['C4'] = 25000
wb.save('data/employee_test.xlsx')

# 测试处理器
import asyncio
from app.rag.document_handler.excel_processor import ExcelProcessor
async def test():
    docs = await ExcelProcessor().process('data/employee_test.xlsx')
    print(f'文档数: {len(docs)}')
    for d in docs:
        print(d.page_content)
asyncio.run(test())
"
```

**企业级验收标准**：

| 验证项 | 要求 | 通过 |
|--------|------|------|
| 文档数 | 2（两张数据行） | |
| 多级表头 | 输出包含 `基本信息 > 姓名张三` 格式 | |
| 合并单元格 | `基本信息 > 姓名` 和 `基本信息 > 职位` 共享父级 | |
| Sheet 上下文 | 输出以 `[Sheet: 员工信息]` 开头 | |

---

### 测试 1.3：代码 AST 切分（多语言）

**测试目的**：验证 Python 和 JS/TS/Java/Go 均能按函数/类正确切分

**测试步骤**：
```bash
cd backend && uv run python -c "
import asyncio, tempfile, os
from app.rag.document_handler.code_processor import CodeProcessor

async def test_lang(ext, code):
    with tempfile.NamedTemporaryFile(mode='w', suffix=ext, delete=False) as f:
        f.write(code)
        tmp = f.name
    docs = await CodeProcessor().process(tmp)
    os.unlink(tmp)
    print(f'{ext}: {len(docs)} chunks')
    for d in docs:
        node = d.metadata.get('node_type', '?')
        print(f'  [{node}] {d.page_content[:60]}...')
    return docs

async def main():
    # Python
    await test_lang('.py', '''
class UserService:
    \"\"\"用户服务\"\"\"
    def login(self, user, pwd):
        return True
    def logout(self, user):
        pass
''')
    # JavaScript
    await test_lang('.js', '''
class UserService {
    login(user, pwd) {
        return true;
    }
    logout(user) {
        return false;
    }
}
function main() {
    console.log('start');
}
''')

asyncio.run(main())
"
```

**企业级验收标准**：

| 验证项 | 要求 | 通过 |
|--------|------|------|
| Python 切分 | ≥2 chunk（class + 方法），含 `class: UserService` 上下文 | |
| JavaScript 切分 | ≥2 chunk，含 `class: UserService` 上下文 | |
| 函数名保留 | chunk 包含 `def: login`、`def: main` 注释 | |
| Fallback | 语法错误的文件退化为空行分块，不崩溃 | |

---

### 测试 1.4：图片 OCR 识别

**测试目的**：验证扫描版 PDF 的 OCR 文字提取和后处理纠错

**测试步骤**：
```bash
cd backend && uv run python -c "
import asyncio
from app.rag.document_handler.ocr_processor import OCRProcessor
async def test():
    # 如果有真实扫描PDF，传入路径测试
    # docs = await OCRProcessor().process('data/scan_report.pdf')
    # 验证基本结构
    op = OCRProcessor()
    print('OCRProcessor 方法:', [m for m in dir(op) if not m.startswith('_')])
    print('后处理字典包含:', op._post_process('白勺'))
    assert op._post_process('白勺') == '的'
    print('OCR 后处理纠错正常')
asyncio.run(test())
"
```

**企业级验收标准**：

| 验证项 | 要求 | 通过 |
|--------|------|------|
| OCR 引擎 | PaddleOCR 可正常加载 | |
| chunk_type 标记 | metadata 含 `chunk_type: "image_ocr"` | |
| 后处理纠错 | `白勺→的`、`己→已` 等常见错字纠正确认 | |

---

## 第二轮：检索策略测试（第三章标准）

### 测试 2.1：查询预处理（压缩 + 拆解 + 扩展）

**测试目的**：验证长问题被压缩、复合问题被拆解、变体被生成

**测试步骤**：
```bash
cd backend && uv run python -c "
import asyncio
from app.rag.query_processor import QueryProcessor

async def test():
    qp = QueryProcessor()
    
    # 测试1：拆解复合问题
    variants = await qp.process('我们公司需要支持多商户、多语言、多货币的电商平台，还要有积分系统和优惠券功能，怎么实现？')
    print(f'拆解后变体数: {len(variants)}')
    for i, v in enumerate(variants):
        print(f'  变体{i+1}: {v[:80]}...')
    assert len(variants) >= 1, '应至少有1个变体'
    
    # 测试2：短问题不变
    variants2 = await qp.process('年假政策')
    print(f'短问题变体数: {len(variants2)}')
    # 短问题可能被扩展但不被压缩

asyncio.run(test())
"
```

**企业级验收标准**：

| 验证项 | 要求 | 通过 |
|--------|------|------|
| 复合问题拆解 | ≥2 个子问题变体 | |
| 短问题不压缩 | 短问题保持原意 | |
| 去重 | 相同变体不重复出现 | |
| HyDE 变体 | main pipeline 中包含 HyDE 生成的假设文档变体 | |

---

### 测试 2.2：粗排召回率（混合检索 + RRF 融合）

**测试目的**：验证向量检索 + BM25 混合检索的召回覆盖率

**测试步骤**：
```bash
cd backend && uv run python -c "
# 1. 先上传已知内容的测试文档到知识库
# 2. 用精确匹配查询验证 BM25 能召回
# 3. 用语义查询验证向量检索能召回
# 4. 对比混合检索 vs 纯向量检索的召回数

# 简易验证：检查检索器初始化
import asyncio
from app.rag.milvus_store import MilvusService

async def test():
    ms = MilvusService()
    # 验证动态权重分类
    w1 = await ms.get_dynamic_weights('员工编号 E12345 的工资')
    w2 = await ms.get_dynamic_weights('公司的年假政策是什么')
    w3 = await ms.get_dynamic_weights('hello')
    print(f'精确查询权重(BM25,Vec): {w1}')  # 预期 BM25 > Vec
    print(f'语义查询权重(BM25,Vec): {w2}')  # 预期 Vec > BM25
    print(f'短查询权重(BM25,Vec):   {w3}')  # 预期 均衡
    assert w1[0] > w1[1], '精确查询应偏重BM25'
    print('动态权重验证通过')

asyncio.run(test())
"
```

**企业级验收标准**：

| 验证项 | 要求 | 通过 |
|--------|------|------|
| 精确查询 | BM25 权重 ≥ 0.6 | |
| 语义查询 | 向量权重 ≥ 0.5 | |
| RRF 融合 | k=60 正确应用 | |
| 去重 | 两路相同文档合并后不重复 | |

---

### 测试 2.3：精排 Reranker 准确性

**测试目的**：验证 BGE Reranker 能正确区分相关和不相关文档

**测试步骤**：
```bash
cd backend && uv run python -c "
import asyncio
from app.rag.reorder_service import reorder_service

async def test():
    query = '怎么申请报销'
    docs = [
        '报销流程：先填写报销单，然后提交给财务部审核。需要部门经理签字。',
        '公司年假政策：员工每年有10天年假，其中5天必须在上半年使用。',
        '报销表格可以在公司内网下载，支持电子签名。',
        '会议室预定系统使用指南：登录后选择时间即可预定。',
    ]
    result = await reorder_service.reorder_documents(query, docs)
    if result['success']:
        print('精排结果（按相关性降序）:')
        for i, d in enumerate(result['documents']):
            print(f'  {i+1}. [{d[\"similarity\"]:.4f}] {d[\"document\"][:60]}...')
        # 验证：报销相关文档应排在年假文档前面
        scores = [d['similarity'] for d in result['documents']]
        assert scores[0] > 0.5, '最相关文档分数应>0.5'
        print('Reranker 测试通过')
    else:
        print(f'失败: {result[\"error\"]}')

asyncio.run(test())
"
```

**企业级验收标准**：

| 验证项 | 要求 | 通过 |
|--------|------|------|
| 相关性区分 | 报销文档 > 年假文档 | |
| 分数归一化 | 输出在 [0, 1] 区间 | |
| 排序稳定性 | 相同输入多次调用结果一致 | |

---

### 测试 2.4：多因素排序

**测试目的**：验证时间衰减、文档权重、类别权重正确生效

**测试步骤**：
```bash
cd backend && uv run python -c "
import asyncio, time
from langchain_core.documents import Document
from app.rag.multi_factor_ranker import MultiFactorRanker

async def test():
    ranker = MultiFactorRanker()
    now = int(time.time())
    one_year_ago = now - 365 * 24 * 3600
    
    # 模拟：旧文档但高相关性 vs 新文档但低相关性
    docs = [
        Document(page_content='旧政策文档', metadata={
            'created_at': one_year_ago, 'doc_weight': 1.0, 'md5': 'old'
        }),
        Document(page_content='新政策文档', metadata={
            'created_at': now, 'doc_weight': 1.0, 'md5': 'new'
        }),
    ]
    # 两者相关性相同，看时间衰减效果
    result = await ranker.rank('政策查询', docs, [0.8, 0.8])
    print('排序结果（新文档应排在前面）:')
    for i, d in enumerate(result):
        print(f'  {i+1}. created_at={d.metadata[\"created_at\"]}, content={d.page_content}')
    assert result[0].metadata['created_at'] == now, '新文档应排第一'
    print('时间衰减验证通过')

asyncio.run(test())
"
```

**企业级验收标准**：

| 验证项 | 要求 | 通过 |
|--------|------|------|
| 时间衰减 | 相同相关性下，新文档 > 旧文档 | |
| 类别权重 | 政策类 (1.0) > 会议纪要 (0.3) | |
| 质量评分 | ingest 后自动计算 quality_score | |

---

## 第三轮：反馈闭环测试（3.7 标准）

### 测试 3.1：反馈权重更新

**测试目的**：验证 like/dislike 能正确影响 DocWeight 表，后续检索体现权重变化

**测试步骤**：
```bash
# 1. 先做一次检索，记录返回的文档
# 2. 对某文档点 like，对另一文档点 dislike
curl -X POST http://127.0.0.1:8000/feedback/batch \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{
    "feedbacks": [
      {
        "session_id": "test-session-001",
        "query": "年假政策",
        "feedback_type": "like",
        "clicked_doc_md5": "文档A的MD5",
        "clicked_doc_filename": "policy_2026.md"
      },
      {
        "session_id": "test-session-001",
        "query": "年假政策",
        "feedback_type": "dislike",
        "clicked_doc_md5": "文档B的MD5"
      }
    ]
  }'

# 3. 查询 DocWeight 表确认权重已更新
cd backend && uv run python -c "
import asyncio
from app.db.db_config import AsyncSessionLocal
from app.models.feedback import DocWeight
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(DocWeight).where(DocWeight.user_id == 'YOUR_USER_ID')
        )
        for dw in result.scalars().all():
            print(f'{dw.doc_filename}: weight={dw.weight:.3f}, '
                  f'impressions={dw.impression_count}, clicks={dw.click_count}, '
                  f'quality={dw.quality_score}')

asyncio.run(check())
"
```

**企业级验收标准**：

| 验证项 | 要求 | 通过 |
|--------|------|------|
| Like 后权重上升 | weight 从初始值上升 | |
| Dislike 后权重下降 | weight 下降但不低于 0.1 | |
| 曝光计数 | impression_count 每次反馈 +1 | |
| 点击计数 | click_count 仅 like 时 +1 | |

---

### 测试 3.2：QueryLog 记录

**测试目的**：验证每次检索自动写入 QueryLog

**测试步骤**：
```bash
# 做一次 RAG 查询后检查 query_log 表
cd backend && uv run python -c "
import asyncio
from app.db.db_config import AsyncSessionLocal
from app.models.feedback import QueryLog
from sqlalchemy import select

async def check():
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(QueryLog).order_by(QueryLog.created_at.desc()).limit(5)
        )
        for ql in result.scalars().all():
            print(f'query={ql.query[:40]}, docs={len(ql.retrieved_docs or [])}, '
                  f'time={ql.created_at}')

asyncio.run(check())
"
```

**企业级验收标准**：

| 验证项 | 要求 | 通过 |
|--------|------|------|
| 自动写入 | 每次 /chat/rag/query 后 query_log 有新记录 | |
| 文档关联 | retrieved_docs 包含 md5 和 source | |

---

## 第四轮：端到端集成测试

### 测试 4.1：完整 RAG 流水线

**测试目的**：验证从上传文档到生成摘要的全链路

**测试步骤**：
```bash
# 1. 上传文档
curl -X POST http://127.0.0.1:8000/knowledge/upload \
  -H "Authorization: Bearer YOUR_JWT" \
  -F "files=@data/policy_2026.md"

# 2. RAG 查询
curl -X POST http://127.0.0.1:8000/chat/rag/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT" \
  -d '{"query": "公司的年假政策是什么？"}'

# 预期返回包含：
# - "documents": 检索到的文档片段列表
# - "summary": LLM 生成的摘要回答
```

**企业级验收标准**：

| 验证项 | 要求 | 通过 |
|--------|------|------|
| 响应时间 | < 10 秒（含 Reranker） | |
| 返回文档数 | ≤ max_documents (8) | |
| 摘要相关性 | 摘要内容与 query 相关 | |
| 错误处理 | 无知识库时返回友好提示 | |

---

### 测试 4.2：图片三路召回联动

**测试目的**：验证含图片的 PDF 被正确 OCR + CLIP 编码 + 可检索

**测试步骤**：
```bash
# 1. 上传含图片的 PDF
# 2. 检查 extracted_images 目录和 Milvus 图片 collection
cd backend && uv run python -c "
from pymilvus import MilvusClient
client = MilvusClient(uri='http://localhost:19530')
# 检查图片 collection
stats = client.get_collection_stats('rag_image_collection')
print(f'图片 collection 行数: {stats.get(\"row_count\", 0)}')
"
# 3. 做包含图片关键词的查询，确认返回结果含 image_visual chunk
```

**企业级验收标准**：

| 验证项 | 要求 | 通过 |
|--------|------|------|
| OCR chunk | metadata 含 `chunk_type: image_ocr` | |
| CLIP 向量 | rag_image_collection 中有对应记录 | |
| 跨模态检索 | 文本查询能召回图片描述结果 | |

---

## 第五轮：性能与稳定性测试

### 测试 5.1：并发检索

```bash
# 使用 Apache Bench 或 wrk
ab -n 50 -c 5 -H "Authorization: Bearer YOUR_JWT" \
   -p query.json -T "application/json" \
   http://127.0.0.1:8000/chat/rag/query
```

**企业级验收标准**：

| 验证项 | 要求 | 通过 |
|--------|------|------|
| 5 并发 50 请求 | 成功率 100% | |
| P95 延迟 | < 15 秒 | |
| 无内存泄漏 | 请求完成后内存回落 | |

---

### 测试 5.2：大文档处理

**测试目的**：验证 100 页 PDF 或 10000 行代码文件能正常处理不崩溃

**企业级验收标准**：

| 验证项 | 要求 | 通过 |
|--------|------|------|
| 大文件不崩溃 | 处理完成或明确报错，不 OOM | |
| chunk 数合理 | 大文件产生 chunk 数与内容量成正比 | |
| 进度回调 | SSE 流式返回进度百分比 | |

---

## 测试通过汇总表

| 轮次 | 测试项 | 权重 | 状态 |
|------|--------|------|------|
| 1.1 | Markdown 标题层级切分 | 中 | ⬜ |
| 1.2 | Excel 合并单元格 + 多级表头 | 中 | ⬜ |
| 1.3 | 代码 AST 切分（多语言） | 高 | ⬜ |
| 1.4 | 图片 OCR 识别 | 中 | ⬜ |
| 2.1 | 查询预处理 | 高 | ⬜ |
| 2.2 | 粗排混合检索 | 高 | ⬜ |
| 2.3 | 精排 Reranker | 高 | ⬜ |
| 2.4 | 多因素排序 | 高 | ⬜ |
| 3.1 | 反馈权重更新 | 高 | ⬜ |
| 3.2 | QueryLog 记录 | 中 | ⬜ |
| 4.1 | 端到端流水线 | 高 | ⬜ |
| 4.2 | 图片三路召回 | 中 | ⬜ |
| 5.1 | 并发检索 | 中 | ⬜ |
| 5.2 | 大文档处理 | 低 | ⬜ |

**全部 14 项通过 → 企业级认证 ✅**

---

## 关键指标看板

| 指标 | 企业级阈值 | 当前值 |
|------|-----------|--------|
| 召回率 (Recall@100) | ≥ 90% | 待测 |
| 精确率 (Precision@10) | ≥ 80% | 待测 |
| MRR (Mean Reciprocal Rank) | ≥ 0.8 | 待测 |
| 查询延迟 (P95) | < 15s | 待测 |
| 文档处理吞吐 | > 10 pages/s | 待测 |
| 反馈闭环生效 | like/dislike 改变后续排序 | 待测 |
| 服务可用性 | 99.5% | 待测 |
