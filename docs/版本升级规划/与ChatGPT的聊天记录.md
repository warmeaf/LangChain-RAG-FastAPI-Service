# 问题

RAG 对精确检索很有用，但是非常不擅长广泛搜索。比如一个简历rag系统，我问：李大乐的学历信息，就能回答的很准确；但是如果我问：请列出所有具有硕士学位的候选人、他们的毕业院校和专业方向。就很有可能遗漏信息，简历越多，问题越严重。明白我的意思不？那么业界针对这种问题，是如何处理的呢？

# 回答

完全明白你的意思，而且这是 **RAG 天生的能力边界**，不是某个向量库或者 Embedding 模型的问题。

实际上，你说的是两类完全不同的查询。

| 查询类型               | 示例          | 最优技术                         |
| ------------------ | ----------- | ---------------------------- |
| Point Lookup（点查询）  | 李大乐学历是什么？   | RAG                          |
| Global Query（全局查询） | 所有硕士候选人有哪些？ | Database / Index / Analytics |

很多团队一开始都会误以为：

> "既然所有简历都放进了 RAG，那为什么不能回答所有问题？"

实际上不能。

---

## 为什么 RAG 做不好这种查询？

举一个极端例子。

假设：

```
100 万份简历
```

Embedding 后：

```
100 万 × chunk
≈ 5000 万 chunk
```

你问：

> 所有硕士候选人

Retriever 会干什么？

它不是：

```
遍历5000万chunk
```

它做的是：

```
找到 Top-K 最相关 chunk

例如：

Top20
Top50
Top100
```

结束。

它永远不会：

```
scan all documents
```

因为 Vector Search 本质就是：

> Approximate Nearest Neighbor Search（ANN）

不是 SQL。

所以：

```
遗漏
```

几乎必然发生。

这也是为什么：

> RAG 不适合 Aggregation。

---

## 业界把这种问题叫什么？

一般叫：

**Global Question**

或者

**Corpus-level Question**

例如：

```
所有……

统计……

列举……

有哪些……

多少……

Top10……

排名……

平均……
```

这些都不是 Retrieval 问题。

而是：

Analysis Query。

---

## OpenAI、Anthropic、Google 怎么做？

目前几乎所有 Agent 都采用：

> Query Routing（查询路由）

而不是：

> 所有问题都走 RAG。

例如：

```
                用户问题
                     │
             Intent Router
          ┌──────────┴──────────┐
          │                     │
     Point Lookup         Corpus Query
          │                     │
      Vector Search      SQL / Graph / Index
          │                     │
          └──────────┬──────────┘
                     │
                    LLM
```

这是目前最主流方案。

---

## 第一种方案：Metadata Filtering（最常见）

简历解析的时候：

不仅做 Embedding。

还抽取结构化信息。

例如：

```
{
    name:"李大乐",
    degree:"硕士",
    school:"浙江大学",
    major:"计算机科学",
    workYears:6,
    city:"北京",
    skills:[
        Java,
        Spring,
        Redis
    ]
}
```

存哪里？

例如：

```
Postgres

MySQL

ElasticSearch

OpenSearch

Mongo

Milvus Metadata

Weaviate Properties
```

用户问：

> 所有硕士

直接：

```
SELECT *

WHERE degree='硕士'
```

而不是：

Vector Search。

这是现在几乎所有招聘系统都这么干。

---

## 第二种方案：Hybrid Retrieval

例如：

```
学历=硕士

技能=Java

工作5年以上
```

Router 会拆成：

```
Metadata Filter

+

Vector Search
```

例如：

```
degree='硕士'

AND

ANN Search
```

Milvus

Qdrant

Weaviate

Pinecone

几乎都支持。

这样：

```
先过滤

再语义搜索
```

效率极高。

---

## 第三种方案：Knowledge Graph

有些企业把简历抽成：

```
Candidate

↓

Education

↓

School

↓

Degree

↓

Major
```

例如：

```
李大乐
    │
    ├──学历
    │
    ├──硕士
    │
    ├──浙江大学
    │
    └──计算机科学
```

用户：

```
所有硕士
```

实际上：

```
MATCH

(candidate)-[:HAS_DEGREE]->(master)
```

Neo4j 很常见。

不过成本较高。

---

## 第四种方案：Document ETL（推荐）

很多企业根本不会：

> "把 PDF 扔进去"

而是：

```
PDF

↓

OCR

↓

LLM Parsing

↓

JSON
```

例如：

```
{
  education:[
    {
      degree:"硕士",
      school:"浙江大学",
      major:"计算机"
    }
  ],
  experience:[
  ],
  skills:[
  ]
}
```

真正查询：

都是查 JSON。

RAG 只是：

```
解释字段

回答开放问题

补全文本
```

不是：

查数据库。

---

## 第五种方案：全文索引（ElasticSearch）

例如：

```
education.degree:"硕士"

education.school:"浙大"
```

Elastic：

```
term query

bool query

aggregation
```

天然支持：

```
count

group by

topN

排序

统计
```

很多 ATS（招聘系统）都是：

```
ES

+

LLM
```

不是：

纯 Vector。

---

## 第六种方案：GraphRAG（微软）

GraphRAG 就是为了解决：

> Global Question。

它会先生成：

```
Community Summary
```

例如：

```
教育背景社区

↓

硕士共有523人

↓

学校分布

↓

专业分布
```

回答：

> 所有硕士

不用扫描全文。

GraphRAG 的论文里大量讨论：

```
Global Search

vs

Local Search
```

Local：

```
李大乐学历？
```

Global：

```
公司有哪些博士？
```

GraphRAG 就是解决第二类。

但是：

GraphRAG 成本很高。

---

## 第七种方案：Agent 自动选择查询方式（目前最先进）

现在几乎所有 AI Agent 都在做：

```
Intent Routing
```

例如：

用户：

```
李大乐学历？
```

↓

```
Vector Search
```

用户：

```
所有硕士
```

↓

```
SQL
```

用户：

```
哪些Java工程师来自985？
```

↓

```
SQL

+

Vector
```

用户：

```
有没有适合腾讯后台开发岗位的人？
```

↓

```
Metadata Filter

+

Vector

+

Rerank
```

用户：

```
给我总结一下这些候选人的优势。
```

↓

```
LLM
```

整个流程：

```
            User Query
                 │
          Intent Classification
                 │
   ┌─────────────┼──────────────┐
   │             │              │
Point Lookup   Aggregation   Analysis
   │             │              │
Vector       SQL / ES / KG   LLM
   │             │              │
   └─────────────┼──────────────┘
                 │
             Final Answer
```

---

## 如果是我设计一个现代 RAG 系统

我会把查询类型分成四类，而不是全部交给向量检索：

| 查询类型                           | 示例                 | 推荐执行方式                      |
| ------------------------------ | ------------------ | --------------------------- |
| **Point Lookup（点查询）**          | 李大乐的学历是什么？         | 向量检索（RAG）                   |
| **Structured Query（结构化查询）**    | 所有硕士、毕业于清华、5 年以上经验 | SQL / Elasticsearch / 元数据过滤 |
| **Analytical Query（分析统计）**     | 各学历人数、专业分布、学校排名    | 数据库聚合（GROUP BY、COUNT 等）     |
| **Open-ended Reasoning（开放推理）** | 推荐最适合某岗位的人并说明原因    | 结构化过滤 + RAG + LLM 推理        |

---

**因此，目前业界的共识已经非常明确：不要把 RAG 当作数据库。** RAG 擅长回答“某个文档里写了什么”，而数据库、搜索引擎和知识图谱擅长回答“整个语料库中有哪些、多少、分布如何”。成熟的 AI 系统通常都会采用 **Query Intent Routing（查询意图路由）**，根据查询类型自动选择 **向量检索、SQL/Elasticsearch、知识图谱或 LLM 推理**，而不是让所有问题都经过同一条 RAG 流程。这也是为什么企业级招聘、法务、医疗等系统，几乎都会同时维护**非结构化索引（RAG）**和**结构化索引（元数据/数据库）**，让两者各自发挥优势。

# 问题

也就是说一个 AI Agent 内容检索系统，不能只有 RAG，还要有其他工具，比如 sql 查询工具，日期查询工具，天气查询工具等，然后要有一套系统提示词：你能干什么，可以使用哪些工具，工作流程是什么，如何验证等，是这样的吧？简短回答我

# 回答

是的，而且这已经是目前生产级 AI Agent 的主流架构。

简化来说就是：

> **LLM ≠ 检索系统，Agent = LLM + 工具 + 路由 + 工作流。**

典型组成包括：

* **RAG**：检索非结构化内容（文档、PDF、知识库）
* **SQL/数据库**：结构化查询、统计、聚合
* **搜索引擎（ES/OpenSearch）**：全文检索、过滤
* **外部 API**：天气、时间、地图、邮件等
* **代码执行器**：计算、数据分析
* **Browser/Web Search**：获取实时信息

然后需要一套明确的 **System Prompt（Agent Operating Manual）**，至少定义：

1. **能力边界**（你有哪些工具）
2. **工具选择策略（Query Routing）**（什么问题用什么工具）
3. **工作流程（Workflow）**（规划 → 执行 → 验证 → 总结）
4. **结果验证（Verification）**（是否完整、是否遗漏、是否需要交叉验证）
5. **失败处理（Fallback）**（工具失败怎么办，是否换工具或询问用户）

所以，现在优秀的 Agent 的核心竞争力，往往已经不是模型本身，而是 **工具体系 + Query Routing + Workflow + Verification**。模型只是其中的“大脑”。


# 问题

那么这样一套内容检索 Agent，应该包含哪些可供 LLM 调用的工具？一一列举出来，并说明理由，举出使用场景

# 回答

如果目标是**企业级内容检索 Agent（Enterprise Content Retrieval Agent）**，我一般不会从"有哪些工具"开始设计，而是从**查询类型（Query Intent）**反推工具。这样不会遗漏，也符合目前主流 Agent 的设计方式。

---

## 一、文档检索类（Document Retrieval）

### 1. RAG / Vector Search（必须）

**作用**

检索非结构化文档。

例如：

* PDF
* Word
* PPT
* Markdown
* Wiki
* Confluence
* 飞书文档

适用场景：

> 李大乐的学历是什么？

> 某需求文档关于权限管理怎么写的？

> XX制度有没有规定？

原因：

RAG 最擅长回答：

> "某个文档里面写了什么。"

---

### 2. Keyword Search（全文检索，ES/OpenSearch）

作用：

关键词精准匹配。

例如：

```
ErrorCode=10021

订单状态

SLA

需求编号
```

适用场景：

> 包含 "退款" 的所有需求。

> 搜索 ErrorCode=10021。

为什么需要？

Embedding 对：

```
编号
ID
版本号
手机号
邮箱
URL
```

效果一般。

全文检索更适合。

---

## 二、结构化查询类（必须）

### 3. SQL 查询工具

作用：

查询数据库。

适用场景：

> 所有硕士候选人

> 近30天订单

> 平均薪资

> Top10客户

原因：

RAG 根本不是做 Aggregation 的。

SQL 天然支持：

```
COUNT

SUM

GROUP BY

ORDER BY

HAVING
```

---

### 4. Metadata Filter

作用：

元数据过滤。

例如：

```
作者

时间

部门

标签

学历

岗位

语言

地区
```

适用场景：

> 北京地区 Java 工程师。

> 2026年的需求。

很多时候：

不用 SQL。

直接：

```
department=研发

AND

year=2026
```

即可。

---

## 三、知识图谱类（可选）

### 5. Graph Query

作用：

实体关系查询。

例如：

```
员工

↓

部门

↓

项目

↓

客户
```

适用场景：

> 李四参与过哪些项目？

> 谁和张三合作最多？

原因：

关系查询。

SQL 很难写。

Graph 更自然。

---

## 四、统计分析类

### 6. Analytics Tool

作用：

统计。

例如：

```
平均

最大

最小

中位数

分布

趋势
```

适用场景：

> 各学历人数。

> 每月新增客户。

> Bug增长趋势。

---

### 7. Code Interpreter（Python）

作用：

复杂计算。

例如：

```
Excel

CSV

JSON

DataFrame
```

适用场景：

> 分析销量。

> 画图。

> 聚类。

> PCA。

> 数据清洗。

很多 BI Agent 都会调用。

---

## 五、实时数据类

### 8. Web Search

作用：

互联网搜索。

适用场景：

> 最新AI新闻。

> OpenAI发布什么？

> 今天苹果股价。

RAG 不知道。

---

### 9. Browser

作用：

浏览网页。

适用场景：

> 登录后台。

> 阅读网页。

> 获取最新公告。

---

### 10. API Tool

作用：

调用业务 API。

例如：

```
天气

地图

航班

ERP

CRM

GitHub

Jira

Slack
```

适用场景：

> 上海天气。

> Jira状态。

> GitHub PR。

---

## 六、时间工具

### 11. Time Tool

作用：

获取：

```
今天

昨天

季度

时区

日期计算
```

适用场景：

> 最近7天。

> 本季度。

> 去年同期。

不要让 LLM 自己算。

---

## 七、文件工具

### 12. File Reader

作用：

读取：

```
PDF

Word

PPT

Excel

Markdown

CSV
```

适用场景：

> 上传一份合同。

> 上传简历。

---

### 13. OCR Tool

作用：

识别：

```
扫描件

截图

照片

表格
```

适用场景：

> 身份证。

> 发票。

> 合同照片。

---

### 14. Parser

作用：

解析：

```
HTML

XML

JSON

Markdown

Office
```

生成：

```
结构化数据
```

例如：

```
Resume

↓

JSON
```

---

## 八、内容生成类

### 15. Summarizer

作用：

总结。

适用场景：

> 总结十份合同。

> 总结所有简历。

---

### 16. Compare Tool

作用：

比较。

适用场景：

> 比较两个版本。

> 两份合同差异。

> 简历对比。

---

### 17. Citation Tool

作用：

返回引用来源。

适用场景：

企业 RAG。

例如：

```
回答：

出处：

PDF

Page12

Paragraph3
```

避免幻觉。

---

## 九、验证类（生产环境非常重要）

### 18. Retrieval Verification

作用：

检查：

```
是否遗漏

是否召回不足

是否需要再次检索
```

例如：

第一次：

```
Top10
```

发现：

```
置信度低
```

自动：

```
Top30
```

再检索。

---

### 19. Fact Verification

作用：

交叉验证。

例如：

```
SQL

+

RAG

+

API
```

三者一致。

可信度更高。

---

### 20. Self Reflection

作用：

Agent 自查。

例如：

```
问题：

列出所有硕士。

回答：

只有8人。

Reflection：

真的只有8人？

是否用了Vector？

是否应该SQL？
```

很多 Agent 框架都会加入这一步。

---

## 十、任务编排类

### 21. Planner

作用：

拆任务。

例如：

> 找出所有硕士，然后统计学校，再推荐三位适合算法岗位的人。

拆成：

```
SQL

↓

统计

↓

RAG

↓

LLM
```

---

### 22. Tool Router（几乎必备）

作用：

决定：

```
什么时候：

SQL

什么时候：

RAG

什么时候：

API

什么时候：

Python
```

这是整个 Agent 的核心。

---

### 一个完整的企业内容检索 Agent 架构

按照能力划分，一个比较完整的工具体系如下：

| 能力域    | 工具                                                           | 典型场景                   |
| ------ | ------------------------------------------------------------ | ---------------------- |
| 非结构化检索 | RAG / Vector Search                                          | 查询文档内容、合同、简历、知识库       |
| 精确检索   | Full-text Search（ES/OpenSearch）                              | 编号、关键字、错误码、全文搜索        |
| 结构化查询  | SQL / Metadata Filter                                        | 条件筛选、统计、聚合、报表          |
| 关系查询   | Graph Query                                                  | 人员关系、组织关系、依赖关系         |
| 数据分析   | Python / Analytics                                           | Excel 分析、图表、复杂计算       |
| 实时信息   | Web Search / Browser / API                                   | 新闻、天气、GitHub、Jira、CRM  |
| 文件处理   | File Reader / OCR / Parser                                   | PDF、图片、扫描件、Office 文档解析 |
| 内容理解   | Summarizer / Compare / Citation                              | 摘要、对比、溯源引用             |
| 质量保障   | Retrieval Verification / Fact Verification / Self Reflection | 防遗漏、交叉验证、结果自检          |
| 智能编排   | Planner / Tool Router                                        | 意图识别、任务拆解、工具选择         |

---

### 我认为真正的核心只有四个

如果让我给一个内容检索 Agent 排优先级，我会认为真正决定系统能力的不是工具数量，而是下面四项：

1. **Query Intent Routing（查询意图路由）**：判断用户到底是在做事实查询、结构化查询、统计分析还是开放式推理。
2. **Tool Selection（工具选择）**：为不同意图选择最合适的工具，而不是默认走 RAG。
3. **Workflow Orchestration（工作流编排）**：复杂问题拆解为多个子任务，按合理顺序执行并组合结果。
4. **Verification（结果验证）**：检查是否存在遗漏、召回不足或数据冲突，必要时自动补充检索或交叉验证。

这四项构成了目前大多数生产级内容检索 Agent 的核心能力；RAG、SQL、OCR、Python 等工具，则是围绕这一核心体系提供具体执行能力。
