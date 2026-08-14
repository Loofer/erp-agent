# RAGAS 评估：让 Agent 从“看起来能回答”变成“可以回归验证”

> 一次演示能证明 Agent 曾经做对过一件事，却不能证明改动之后它仍然做对。Motorparts Agent 同时依赖知识库检索、工具选择、子 Agent 委派和最终回答，只看回复是否流畅，无法定位问题发生在召回、工具调用还是生成阶段。RAGAS 评估的价值，是把这条链路变成可重复、可诊断的实验。

用户问“BP-100 的库存是否需要补货”，正确回答既要包含当前库存和安全库存，也要调用库存工具；用户问“BP-100 适配哪个电机平台”，则需要从知识库取得兼容性和最小起订量。前者的错误通常是没有取实时数据，后者的错误可能是检索漏召、改写丢失型号，或回答没有被检索证据支持。

当前评估不会只判断“答案像不像参考答案”，而是同时记录回答、检索证据、工具轨迹、延迟和评委的理由。

## 一、为什么 Agent 评估不能只有一个分数

RAG 和 Agent 任务的失败不是同一种失败：

| 现象 | 可能原因 | 只看最终答案的盲区 |
| --- | --- | --- |
| 回答有正确事实但没有依据 | 模型猜中或使用了未记录的信息 | 无法识别幻觉风险 |
| 找到很多文档但回答不相关 | 召回噪声、重排不足或生成偏离问题 | 不知道该优化检索还是提示词 |
| 回答正确却漏调用 Motorparts 工具 | 测试数据或模型知识恰好覆盖了答案 | 无法发现生产环境的数据时效风险 |
| 调用了正确工具但回答错误 | 工具结果未被理解、汇总或引用 | 不能区分工具选择与答案生成问题 |

因此，当前实现组合了五项 LLM 驱动的 RAGAS 指标和一项确定性的工具指标。它们不是互相替代，而是从“证据、答案、工具”三个维度交叉判断 Agent 行为。

## 二、评估运行的是生产编排，而不是简化 Demo

评估入口是 [`backend/evals/run.py`](../../evals/run.py)，通过 [`runner.py`](../../evals/runner.py) 加载生产 `load_agent_graph()` 和 `ChatService`，不启动 FastAPI。它复用当前的主 Agent、子 Agent、RAG 改写、混合检索和请求前上下文注入，因此能暴露真实编排的回归。

为避免评估产生 Motorparts 写操作，运行链路替换了生产 HTTP 客户端：

```text
评估数据集
  │
  ▼
生产 Agent 图与 ChatService
  ├─ RAG ───────────────► 已配置的 Zilliz/Milvus 集合（实时）
  └─ Motorparts 工具 ──────────► MockTransport 只读 Fixture
                              ├─ GET：返回固定供应商、物料、订单和库存数据
                              └─ 非 GET：返回 405
  │
  ▼
事件流、检索快照和工具结果
  │
  ▼
RAGAS Judge + tool_correctness
  │
  ▼
CSV、控制台汇总和逐样本诊断
```

[`fixtures/motorparts.py`](../../evals/fixtures/motorparts.py) 会记录每个请求，并拒绝 `POST`、`PUT` 等写操作。创建、更新和人工审批（HITL）不在这套离线评估范围内；即使 Agent 路由错误，也不会改变 Motorparts 状态。

## 三、证据怎样进入 RAGAS

RAGAS 需要看到“回答基于什么”。当前实现不会只传入向量检索片段，也不会只传 Motorparts 工具结果，而是将两类可观察证据合并：

```text
retrieved_contexts =
    Zilliz 命中的父块内容
    + 已完成 Motorparts 工具调用的返回结果
```

[`RecordingRetriever`](../../evals/rag_recording.py) 包装当前 `HybridRetriever`，记录最终父块的 `parent_id`、内容和四视角查询：`original`、`semantic`、`keyword`、`intent`。`extract_trace()` 则从事件流提取：

- 主 Agent `motorparts-agent` 的最终文本；
- 实际发生的工具调用；
- 除 `search_knowdge` 外已完成工具的返回内容；
- Agent 错误或意外 HITL 中断。

把工具返回加入证据，使同一套 RAGAS 指标可覆盖知识问答和只读 Motorparts 问答。但它也意味着解读指标时必须看任务类别：Motorparts 查询的 `faithfulness` 表示回答是否被工具返回支持，知识问答的 `faithfulness` 更接近回答是否被检索文档支持。

## 四、六项指标分别回答什么问题

[`judge.py`](../../evals/judge.py) 为每项 RAGAS 指标只传入其需要的字段，避免把不相关信息混入评分输入。

| 指标 | 输入 | 主要回答的问题 | 低分时优先检查 |
| --- | --- | --- | --- |
| `faithfulness` | 问题、回答、证据 | 回答中的主张能否由检索块或工具返回支持？ | 幻觉、证据遗漏、工具结果未被引用 |
| `answer_relevancy` | 问题、回答 | 回答是否真正回应用户问题？ | 意图理解、答非所问、无关冗长内容 |
| `context_precision` | 问题、参考答案、证据 | 召回证据是否大多与目标答案相关？ | 查询改写噪声、BM25/Dense 候选、重排 |
| `context_recall` | 问题、参考答案、证据 | 证据是否覆盖回答所需事实？ | 漏召回、切块、索引、过滤条件 |
| `answer_correctness` | 问题、回答、参考答案 | 回答是否与人工参考在事实和语义上相符？ | 生成、汇总、格式或参考答案质量 |
| `tool_correctness` | 期望工具、实际工具 | 是否选择了完成业务任务所需的工具集合？ | 路由、委派、工具说明和 Skill 流程 |

前五项由独立 Judge 模型异步调用 RAGAS 0.4.3 计算；`answer_relevancy` 与 `answer_correctness` 还使用 Judge Embedding。第六项不调用 LLM，而是使用 Jaccard 相似度：

```text
tool_correctness = |expected ∩ actual| / |expected ∪ actual|
```

其中内部路由工具 `task` 会从 `actual` 集合中移除。因而“期望 `inventory_warning` 和 `order_search_details`，实际只调用前者”的分数为 `0.5`，而不是模糊的主观判断。

## 五、评估集不是提示词样例集

默认数据集 [`agent_smoke.json`](../../evals/datasets/agent_smoke.json) 有六个经审查的中文只读样本：知识库问答、供应商查询、物料查询、订单查询、库存预警和多工具采购分析。每个样本包含：

```json
{
  "id": "analysis-001",
  "category": "procurement_analysis",
  "input": "结合 BP-100 的库存预警和历史采购订单，给出补货建议。",
  "reference_answer": "...",
  "expected_tools": ["inventory_warning", "order_search_details"],
  "required_facts": ["8", "20", "补货"],
  "grading_notes": "..."
}
```

`load_dataset()` 要求以上七个字段，并拒绝空数据集、缺字段和重复 ID。`required_facts` 与 `grading_notes` 目前用于维护者审查和故障定位，RAGAS Judge 的五项评分实际使用 `input`、`response`、`reference_answer` 与 `retrieved_contexts`；不能误以为填写了 `required_facts` 就已经产生自动硬校验。

扩充评估集时，应覆盖以下组合，而不是只增加换一种说法的简单问题：

| 类别 | 应覆盖的变化 |
| --- | --- |
| RAG 知识问题 | 口语别称、精确型号、否定条件、多约束和无答案问题 |
| 只读 Motorparts 查询 | 供应商、物料、订单、库存与字段缺失情况 |
| 多工具分析 | 工具顺序、工具缺失、数据不足与保守结论 |
| 路由与安全 | 不应调用写工具、意外 HITL、无法提供实时事实时的提示 |

## 六、如何运行与阅读结果

先安装可选依赖：

```powershell
uv sync --project backend --extra evals
```

配置正常 Agent 与 RAG 所需变量，并单独配置 Judge：

```dotenv
RAGAS_JUDGE_API_KEY=
RAGAS_JUDGE_BASE_URL=https://api.openai.com/v1
RAGAS_JUDGE_MODEL=gpt-5.4-mini
RAGAS_JUDGE_EMBEDDING_MODEL=text-embedding-3-small
```

Judge 端点必须同时支持 Chat Completions 和 Embeddings；`ZILLIZ_URI`、`ZILLIZ_TOKEN`、`MILVUS_COLLECTION` 缺失时，评估在样本运行前失败。RAGAS 0.4.3 依赖 `langchain-community>=0.3.31,<0.4`，这个版本范围已固定在 `pyproject.toml` 的 `evals` 可选依赖中。

`RagasJudge` 以独立的 `RAGAS_JUDGE_*` 配置创建 Judge LLM 和 Embedding 客户端，避免与待测 Agent 模型混为同一个配置来源。每项指标的异常由该类封装为单项失败，不会中止剩余样本或其他指标的评分。

从仓库根目录执行：

```powershell
uv run --project backend --extra evals python -m backend.evals.run
```

指定数据集和输出路径：

```powershell
uv run --project backend --extra evals python -m backend.evals.run `
  --dataset backend/evals/datasets/agent_smoke.json `
  --output backend/evals/experiments/manual.csv
```

使用 `--no-judge` 时，仍会运行生产 Agent、记录轨迹并计算 `tool_correctness`，但五项 RAGAS 分数会标记为未评分。它适合先检查工具路由、Agent 异常和原始证据，不能用来判断回答质量。

CSV 以 UTF-8 BOM 写入，包含以下诊断信息：

```text
输入、模型、最终回答、期望/实际工具、检索父块 ID、合并证据、
五项 RAGAS 分数及原因、工具正确性、延迟、Agent 错误、Judge 错误
```

Judge 单项失败不会终止整次实验：该项分数写为 `None`，原因是 `Metric failed`，具体异常保存在 `judge_error`。Agent 执行失败或意外进入 HITL 时，五项 Judge 评分均跳过，并在 `agent_error` 中保留原因。

## 七、不要用平均分掩盖回归

一次模型、提示词、Skill、改写、索引或重排调整后，应首先比较相同数据集的逐行结果，再看总体均值：

```text
基线实验
  → 修改单个变量
  → 重跑相同数据集
  → 按 category、指标和失败样本对比
  → 回看 retrieved_ids、actual_tools、reason 与错误字段
```

常见诊断路径如下：

| 症状 | 可能解释 | 下一步 |
| --- | --- | --- |
| `context_recall` 降、`faithfulness` 正常 | 回答只使用了少量证据，但关键事实没有完全召回 | 检查切块、索引、过滤和查询改写 |
| `context_precision` 降、`context_recall` 正常 | 关键材料仍能找到，但候选噪声增加 | 检查改写重复、Dense/Sparse 配比和重排 |
| `faithfulness` 降、`answer_correctness` 尚可 | 答案可能恰好接近参考，却没有可追溯证据 | 检查回答约束、检索上下文和工具结果使用 |
| `tool_correctness` 降、RAG 分数正常 | 文档问答表现稳定，但 Motorparts 路由或委派发生回归 | 检查主 Agent Memory、子 Agent描述和 Skill 前置流程 |
| `answer_relevancy` 降，证据指标正常 | 找到了材料却没有直接回答用户目标 | 检查意图改写、回答提示与最终汇总 |
| `judge_error` 增多 | Judge API、模型兼容性或 Embedding 配置异常 | 先修复 Judge，再比较回答指标 |

## 八、可重复性与边界

Motorparts fixture 是固定的，Agent 图和评估集也可版本控制；但 Zilliz/Milvus 集合保持在线。因此集合内容、Embedding 模型、查询改写权重、混合检索参数或 Reranker 改动，都可能改变 RAG 样本的分数。

这不是评估缺陷，而是需要记录的实验条件。每次对比至少记录：运行时间、Agent 模型、Judge 模型、Judge Embedding、数据集版本、集合或索引版本，以及是否启用 Reranker。对于候选模型对比，应固定这些条件和数据集，避免把知识库变化误判为模型提升。

> 一句话结论：RAGAS 不是给 Agent 打一个总分，而是把“回答是否有证据、证据是否找对、工具是否调用正确、最终答案是否满足问题”拆成可回归的诊断面；只有结合逐样本轨迹，分数才会变成可执行的优化方向。
