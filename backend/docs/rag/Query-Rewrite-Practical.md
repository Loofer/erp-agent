# 问题改写：让 RAG 从“搜得到词”变成“找得到答案”

> 用户只会用自己的语言提问，知识库却按文档作者的语言组织。问题改写的价值，不是把一句话说得更漂亮，而是在检索前补齐这两种语言之间缺失的表达路径。

在汽配 ERP 知识库中，用户可能问“P-100 的刹车皮能不能装”，而文档写的是“P-100 制动片适配关系”“刹车片兼容车型”或“制动系统安装规范”。如果只拿原句检索，精确型号或许能命中，但“能不能装”背后的兼容性、适配性、安装条件未必进入候选集；如果用户只问“这个东西咋退”，文档里的“退货申请”“售后流程”“退款规则”又可能全部漏掉。

问题改写解决的正是这个召回缺口。

## 一、为什么原始问题不够用

一个查询通常同时包含几种不同信号，但它们适合不同检索方式：

| 信号 | 用户说法 | 知识库可能使用的说法 | 主要风险 |
| --- | --- | --- | --- |
| 精确实体 | `P-100`、`ORD-9527` | 相同型号、订单号、错误码 | 改写时被丢失或变形 |
| 业务意图 | “能不能装” | 适配、兼容、安装条件 | 文本词面不重叠 |
| 领域同义词 | “刹车皮” | 制动片、刹车片 | 向量或 BM25 只覆盖其中一部分 |
| 约束条件 | “今天到货”“只看上海仓” | 发货时效、仓库、库存地 | 泛化改写后约束丢失 |

向量检索能处理一部分语义差异，却容易弱化型号、零件号、日期和状态；BM25 擅长精确字面命中，却不理解“退货”和“申请售后”是相近动作。因此，单独换一个更强的 Embedding 模型，通常无法消除这两类漏召。

> 正确目标不是寻找“最好的那一句查询”，而是生成一组彼此互补、同时受约束的查询。

## 二、四视角改写：保守扩展，而非自由改写

当前 RAG 的思路是保留原问题，再从三个明确视角扩展。以用户问题为例：

```text
原始问题：P-100 的刹车皮能不能装到 X2 上？

original：P-100 的刹车皮能不能装到 X2 上？
semantic：P-100 制动片与 X2 车型是否兼容、是否适配
keyword：P-100 X2 刹车片 制动片 兼容 适配
intent：查询 P-100 制动片安装到 X2 车型的适配关系、限制条件和依据
```

四个视角各自解决一个问题：

| 视角 | 解决什么 | 不应做什么 |
| --- | --- | --- |
| `original` | 保留用户全部原意、实体和措辞 | 不能省略 |
| `semantic` | 将口语、别称转成领域表达 | 不能编造不存在的零件或车型 |
| `keyword` | 提取型号、编号、状态、筛选词 | 不能丢掉或改写精确编码 |
| `intent` | 补全业务动作、目标和约束 | 不能把问题提前回答掉 |

这比“让 LLM 生成 5 个类似问法”更可控。任意同义改写常常只是制造重复候选；按视角改写则分别服务语义覆盖、精确匹配和业务目标理解。

## 三、原始问题必须是第一公民

改写模型会犯错：把 `P-100` 误成 `P100`，把“上海仓”泛化成“附近仓库”，或忽略“仅适用于 2024 款”这样的限制。原始问题因此绝不能被替换，只能作为最高优先级的一路。

实践上应遵循三条规则：

1. 原始问题始终参与检索，且融合权重最高。
2. 改写为空、与原句相同或与其他改写重复时去重，避免徒增检索调用。
3. 改写服务不可用、返回非 JSON 或字段不完整时，所有改写回退为原问题，检索不应失败。

当前实现使用的权重为 `original=1.00`、`keyword=0.90`、`intent=0.85`、`semantic=0.80`。这表达了一个偏保守的判断：ERP 场景的实体与约束比泛化语义更容易决定答案正确性。

## 四、改写不是替代混合检索，而是放大它

每一个查询视角都同时走 Dense 和 BM25 两个通道。完整的 4 x 2 路径如下：

```text
                         ┌─ Dense：语义相近的说明、规则、问答
original  ───────────────┤
                         └─ BM25：P-100、X2 等字面精确命中

                         ┌─ Dense：制动片 / 适配 / 兼容的语义覆盖
semantic  ───────────────┤
                         └─ BM25：领域别名带来的额外字面命中

                         ┌─ Dense：型号与动作的组合语义
keyword   ───────────────┤
                         └─ BM25：型号、零件号、状态等强信号

                         ┌─ Dense：完整业务目标与条件
intent    ───────────────┤
                         └─ BM25：目标中的关键约束词
```

这样做的关键收益是“交叉验证”。某个父文档如果同时被原问题的 BM25、语义改写的 Dense、意图改写的 Dense 召回，它比只在某一路偶然出现的候选更值得排在前面。

## 五、用加权 RRF 合并多路结果

不同通道的原始分数不可直接比较：余弦相似度与 BM25 分数不在同一量纲，改写查询之间的分数分布也会变化。加权 Reciprocal Rank Fusion（RRF）只使用每一路内部的名次，因此稳定且易于解释：

```text
score(chunk) = Σ query_weight / (60 + rank)
```

其中 `rank` 是该子块在某一路中的名次，`60` 是平滑常数。一个子块多次出现会累计分数，再按 `child_id` 去重。随后把命中的子块合并回父块，并对父块进行可选的 Cross-Encoder 重排。

这形成了清晰的分工：

```text
问题改写       扩大表达覆盖面
Dense + BM25    补齐语义与精确词两类盲区
加权 RRF        奖励多路一致命中的内容
Parent 扩展     让模型拿到足够完整的上下文
Reranker        在有限候选中判断“是否真正回答问题”
```

## 六、源码如何实现这套思路

以下片段来自当前代码，可作为本文方案的直接落点。

### 1. 改写输出受固定契约约束

[`query_rewriter.py`](../../src/agent/rag/query_rewriter.py) 不让模型自由发挥，而是要求固定的三个字段，并明确“不要回答问题”。解析失败时回退原查询：

```python
_SYSTEM_PROMPT = """Return only JSON with semantic, keyword, and intent fields.
semantic expands business synonyms and fixes phrasing. keyword preserves exact
model numbers, part numbers, states, and filter fields. intent preserves the
user's full business objective and constraints. Do not answer the question."""

def rewrite(self, query: str) -> QueryVariants:
    try:
        response = self._model.invoke([...])
        parsed = json.loads(content if isinstance(content, str) else "")
        return QueryVariants(
            query,
            _string_value(parsed, "semantic", query),
            _string_value(parsed, "keyword", query),
            _string_value(parsed, "intent", query),
        )
    except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
        return QueryVariants(query, query, query, query)
```

`QueryVariants.items()` 还会对空值和重复改写去重。因此降级后最终只检索一次原问题，而不是产生四份相同查询。

### 2. 每个有效视角都走 Dense 与 Sparse

[`hybrid_retriever.py`](../../src/agent/rag/hybrid_retriever.py) 的主流程对应前文的 4 x 2 路设计。`RetrievalConfig` 默认让每条通道取 20 个子块，融合后取 30 个，再缩到 12 个父块和 3 条上下文：

```python
_QUERY_WEIGHTS = {
    "original": 1.0,
    "semantic": 0.8,
    "keyword": 0.9,
    "intent": 0.85,
}

def retrieve(self, query: str) -> RetrievalResult:
    variants = self._query_rewriter.rewrite(query)
    rankings = []
    for query_type, rewritten_query in variants.items():
        rankings.append(self._search_channel(rewritten_query, query_type, "dense"))
        rankings.append(self._search_channel(rewritten_query, query_type, "sparse"))
    fused = weighted_rrf(rankings, self._QUERY_WEIGHTS, constant=60, limit=30)
    candidates = expand_parents(fused, self._search_store, limit=12)
    context = rerank_parents(query, candidates, self._reranker, limit=3)
    return RetrievalResult(variants=variants, context=tuple(context))
```

注意重排器接收的是原始用户问题，而不是某个改写版本。这能避免改写中的泛化表述主导最终相关性判断。

### 3. RRF 只融合排名，不混合不可比的原始分数

[`retrieval.py`](../../src/agent/rag/retrieval.py) 中每个子块按 `child_id` 汇总多路证据，保留 `query_type`、`channel` 和名次，既可解释也便于后续做召回诊断：

```python
for ranking in rankings:
    for hit in ranking:
        weight = weights.get(hit.query_type, 1.0)
        scores[hit.child.child_id] += weight / (constant + hit.rank)
        by_child[hit.child.child_id].append(hit)

return sorted(fused, key=lambda hit: (-hit.score, hit.child.child_id))[:limit]
```

### 4. 请求前预取让改写结果自然进入回答上下文

[`chat_service.py`](../../src/api_view/chat_service.py) 在有新用户消息时，在线程池运行同步检索器；失败只记录日志，不阻断会话：

```python
if message is not None and self._rag_retriever is not None:
    try:
        retrieval = await asyncio.to_thread(self._rag_retriever.retrieve, message)
        context["retrieval_context"] = render_retrieval_context(retrieval.context)
    except Exception:
        _log.exception("RAG retrieval failed for thread %s", thread_id)
```

[`runtime.py`](../../src/agent/rag/runtime.py) 负责把 Zilliz/Milvus、Embedding、改写模型和可选本地 Reranker 组装为同一个 `HybridRetriever`。重排模型无法加载时只关闭重排，不关闭改写与混合检索。

## 七、哪些问题适合改写，哪些需要收紧

### 口语化、短问题：应该积极扩展

```text
“这个东西咋退？”
```

适合扩展为“退货流程”“售后申请”“退款规则”“退换货条件”。原句短、业务意图明确但词面信息不足，改写往往显著增加召回覆盖。

### 型号、订单号、日期、金额：应以保真为先

```text
“ORD-9527 今天能从上海仓发吗？”
```

此类问题的 `keyword` 视角应保留 `ORD-9527`、`今天`、`上海仓`，`intent` 也不能把它简化为“查询订单配送状态”。精确字段一旦丢失，语义再接近也可能检索到错误订单或错误仓库。

### 已有结构化过滤条件：不要用改写取代过滤

若系统已能按租户、文档类型、车型、仓库或权限过滤，过滤必须在检索时执行。问题改写只能补充文本表达，不能承担权限控制和精确字段筛选。

### 需要实时 ERP 数据：不要把 RAG 当事实源

“当前库存”“订单是否已发货”“今天的价格”需要调用已注册 ERP 工具。改写后的知识库检索可用于找流程、规则和字段含义，不能替代实时业务数据查询。

## 八、常见失败模式

| 失败模式 | 表现 | 改进方式 |
| --- | --- | --- |
| 改写过度泛化 | `P-100` 被改成“制动零件” | 原句保留最高权重；提示词要求精确实体原样保留 |
| 多条改写同义重复 | 四路得到几乎相同候选 | 对规范化后的改写去重 |
| 改写直接回答问题 | 模型将假设当作检索条件 | 明确要求“只改写，不回答” |
| 只改写不保留原句 | 型号、日期、否定条件丢失 | 原问题固定为一路 |
| 只走向量通道 | 型号、订单号、状态召回差 | 每个视角均走 Dense + BM25 |
| 直接相加检索分数 | 某一通道分数尺度主导排序 | 使用 RRF 等基于名次的融合 |
| 扩展无限增多 | 延迟、噪声、成本同步上升 | 限定为少量互补视角，先测再扩 |

## 九、如何判断改写真的有效

不要只看“回答看起来更好”。应准备包含口语别称、精确型号、业务规则、否定条件和多约束组合的离线问题集，并比较以下指标：

| 指标 | 说明 |
| --- | --- |
| Recall@K | 正确文档是否进入前 K 个候选，是改写最直接的指标 |
| MRR / nDCG | 正确文档是否被排到更前面，验证融合与重排效果 |
| 零结果率 | 改写后无候选的问题比例，应下降而非上升 |
| 精确实体保留率 | 型号、订单号、日期、仓库等是否在改写中保真 |
| p50 / p95 延迟 | 改写增加模型调用和检索路数，必须观察尾延迟 |

推荐做一个简单消融实验：`原问题`、`原问题 + 双通道`、`四视角 + 双通道`、`四视角 + 双通道 + Reranker`。只有第四组相对前几组在目标问题集上提升，才值得承担额外延迟与成本。

## 十、当前落地方式

项目中的 `JsonQueryRewriter` 输出 `semantic`、`keyword`、`intent` 三类改写；`HybridRetriever` 保留原问题，对每个有效视角执行 Dense 和 Sparse 检索，使用上述权重进行 RRF 融合，再展开父块并重排。查询改写或重排不可用时，系统退化为使用原问题的混合检索，而不是让整个对话失败。

> 一句话结论：问题改写不是让查询变长，而是让同一个问题同时拥有“用户原话、领域语言、精确词表和业务目标”四种入口；再用混合检索与融合排序，把这些入口汇成更完整、更可靠的候选集。
