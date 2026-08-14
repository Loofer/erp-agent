# Chart 输出：让分析结果成为受控的前端图表数据

> 采购分析需要展示趋势、对比和构成，但图表不应由 Agent 生成图片、HTML 或任意 ECharts 配置。该设计把 Agent 的职责收敛为输出可验证的结构化数据，再由服务端决定如何交给前端渲染。

在采购场景中，Agent 可能已从 Motorparts 历史订单中算出各供应商的平均采购价。若让它生成 PNG，后端需要处理文件保存、访问路径、清理和安全问题；若让它直接生成 ECharts option，模型又可能输出任意 JavaScript 配置。更可靠的边界是：`execute` 只输出一条 chart JSON，后端只接受预定义字段，前端只消费服务器生成的安全 payload。

## 一、Chart 不是报告格式

Chart JSON 只传输可视化所需的数据，不能承载分析过程、报告正文、内部文件路径或 HTML。复杂采购报告仍由 `write_file` 写入 `/analysis/report_{timestamp}.md`；主 Agent 读取报告后组织用户可见的结论。

这对应明确的职责划分：

| 组件 | 负责 | 不负责 |
| --- | --- | --- |
| Motorparts 工具 | 返回供应商、物料、订单、库存等真实业务数据 | 推断缺失价格、交期或评分 |
| `execute` | 聚合数据，按 NDJSON 输出可选图表 | 生成图片、HTML、报告文件 |
| `visualization.schema` | 校验 chart JSON 的类型、大小和字段关系 | 计算采购指标 |
| `visualization.echarts` | 将已验证的规格确定性转换为 ECharts option | 接受模型生成的 option |
| 主 Agent | 汇总结论，原样转发子 Agent 的 chart JSON | 改写或拼装 chart JSON |

因此，普通计算无需使用 chart 协议。例如 `average_price=12.3` 是合法的普通 `execute` 输出；只有前端需要渲染图表时，才输出 chart JSON。

## 二、单行 NDJSON 是 Agent 与后端的边界

首次需要生成图表前，采购分析 Agent 必须读取 [`chart_params.md`](../../skills/procurement/procurement-analysis/reference/chart_params.md)。它规定每个图表文档是一条完整 JSON 行，而不是带前缀的日志、Markdown 代码块或 ECharts 配置。

```json
{"type":"chart","version":"1.0","charts":[{"id":"supplier-price","chart_type":"bar","title":"供应商平均采购价","x":"supplier_name","y":"average_price","data":[{"supplier_name":"供应商A","average_price":12.3}],"provenance":["order_search_details"],"warnings":[]}]}
```

一条执行输出可以包含普通日志和 chart 行：解析器逐行扫描，只尝试解析去除首尾空白后以 `{` 开头的行。普通日志或无效 JSON 会被忽略；一旦某个 JSON 对象声明 `"type":"chart"`，它就必须完全符合 v1.0 契约，否则抛出 `ChartDocumentError`。这让“没有图表”保持宽容，让“声称是图表但格式错误”能够被识别和纠正。

```text
calculation complete
{"type":"chart","version":"1.0","charts":[...]}
```

## 三、v1.0 契约限制了什么

[`schema.py`](../../src/visualization/schema.py) 将 `chart_type` 限定为 `bar`、`line`、`pie`、`table`、`kpi`，并禁止未声明字段。单个文档必须有 1 至 12 个图表；每个图表的关键约束如下。

| 字段 | 约束与含义 |
| --- | --- |
| `id` | 必填，1 至 120 个字符；用于稳定标识图表 |
| `chart_type` | 必填，仅允许五种受支持类型 |
| `title` | 必填，1 至 200 个字符 |
| `subtitle` | 可选，最长 300 个字符 |
| `x`、`y` | `bar`、`line`、`pie` 必填；值为 `data` 行中的字段名 |
| `data` | 最多 500 行；每行最多 30 个字段；坐标类图表每一行都必须拥有 `x`、`y` 指定字段 |
| `provenance` | 最多 30 项，记录数据来自哪些 Motorparts 工具，例如 `order_search_details` |
| `warnings` | 最多 30 项，记录样本不足、时间范围不完整等限制 |
| `chartable` | 默认 `true`；为 `false` 时保留结构化数据，但不请求 ECharts 渲染 |

`table` 和 `kpi` 不要求 `x`、`y`，用于明细行和关键指标。`pie` 也使用 `x`、`y`，前者映射扇区名称、后者映射数值。未被 v1.0 支持的雷达图、散点图、热力图和任意自定义 option 都不得输出。

## 四、LLM 会写错 JSON，验证负责守住渲染边界

LLM 即使理解了业务数据，也可能在输出时漏掉逗号、引号或括号，或把字段名写成近似但不受支持的形式。图表协议不能把“模型大多数时候能输出正确 JSON”当作前提；稳定性来自后端只让同时通过 JSON 解析和 schema 校验的数据进入后续渲染。

| LLM 输出问题 | 解析或校验结果 | 对受控渲染链路的影响 |
| --- | --- | --- |
| 漏逗号、漏引号、括号不配对 | `json.loads()` 失败，该行不是有效 chart 文档 | 不产生 `ChartSpec`，不会生成 ECharts option |
| `type` 不是 `chart` | 视作普通 JSON 行 | 不进入图表处理 |
| 声明 `"type":"chart"` 但缺少必填字段、版本错误或有额外字段 | `ChartDocument.model_validate()` 失败，并抛出 `ChartDocumentError` | 调用方必须拒绝或要求 Agent 修正，不能降级为任意 option |
| `bar`、`line`、`pie` 的数据行缺少 `x` 或 `y` 指向字段 | `ChartSpec.model_post_init()` 校验失败 | 防止坐标轴与数据序列不一致 |
| 数据行、图表数或字段数超限 | Pydantic 字段长度或行校验失败 | 限制单次输出的资源占用 |

这种强约束把失败限制在“当前图表无法被接受”，而不是把不完整或畸形的数据带到浏览器。Agent 收到格式错误后应重新读取 `chart_params.md`，修复 JSON 与字段后再输出；它不应通过输出 HTML、图片或自定义 ECharts option 绕过校验。

需要区分两层行为：`parse_chart_documents()` 当前对无法解析的 JSON 行采取忽略策略，使含有普通日志的 `execute` 输出不会中断；对已经明确声明 `"type":"chart"` 但结构不合规的对象则严格报错。这一校验能力只有在调用方接入解析器后才能成为线上保护，当前聊天事件路径仍会原样透传 `execute` 的 stdout，详见“当前代码的真实运行状态”。

## 五、多 Agent 交接时必须原样透传

采购分析子 Agent 生成 chart JSON 后，结果还要经过主 Agent 才会形成最终回复。这个交接点同样可能破坏 JSON：主 Agent 可能翻译字段名、为数据补充说明、把 JSON 放进代码块、转义引号，或只摘录其中一部分。对自然语言回答而言这些改写通常无害，对前端图表协议却可能造成解析失败或改变数据含义。

因此，主 Agent 的系统提示在 [`prompts.py`](../../src/agent/memory/prompts.py) 的 `Resources & Boundaries` 中明确要求：当子 Agent 返回 chart JSON 时，最终回复必须包含**完整且未改变**的 JSON，供前端 ECharts 渲染。该规则与“子 Agent 返回报告或文本文件路径时，主 Agent 必须先 `read_file` 再面向用户作答”的规则并列：报告内容需要被读取、组织和解释，chart JSON 则是机器可识别载荷，不能参与这类改写。

`build_system_prompt()` 在 Agent 图构建时提供稳定提示；`build_request_system_prompt()` 在每次请求时使用同一模板，并额外注入用户、时间和检索上下文。因此，原样透传 chart JSON 不是某个采购任务的临时提示，而是主 Agent 的全局交付约束。采购分析子 Agent 的配置也使用相同要求，形成以下交接规则：

```text
子 Agent：从 execute 结果中取得完整 chart JSON
     -> 不添加报告正文或 ECharts option
主 Agent：可组织结论文本
     -> chart JSON 不翻译、不重排、不截断、不加 Markdown 包装
前端：从原样 JSON 识别并渲染图表
```

主 Agent 的约束不是替代 schema 验证，而是保护已经生成的协议载荷在多 Agent 传递中的字节级结构。提示词只能约束模型行为，不能像程序校验一样保证每次输出正确；因此仍需要后端接入解析器与 schema。两者共同降低风险：子 Agent 按契约生成，主 Agent 不改写，后端再做结构校验和确定性转换。任何图表数据变更都应回到 `execute` 重新计算并输出新的完整文档，不能由主 Agent 手工编辑 JSON。

## 六、为什么 ECharts option 不能由模型输出

[`echarts.py`](../../src/visualization/echarts.py) 是唯一将 `ChartSpec` 转成 ECharts option 的位置。它只从已验证的字段读取类别和值，并固定配色、标题、提示框和网格：

```python
if spec.chart_type in {"bar", "line"}:
    base.update(
        {
            "xAxis": {"type": "category", "data": [row.get(spec.x, "") for row in spec.data]},
            "yAxis": {"type": "value"},
            "series": [{
                "name": spec.y,
                "type": spec.chart_type,
                "data": [row.get(spec.y) for row in spec.data],
                "smooth": spec.chart_type == "line",
            }],
        }
    )
```

`bar` 与 `line` 生成一条序列，`line` 固定开启平滑；`pie` 生成名称和值组成的扇区数据，并固定环形半径。`table`、`kpi` 或 `chartable=false` 不产生 ECharts option，以便前端根据原始 `spec` 渲染表格、指标卡或降级内容。

[`renderer_contract.py`](../../src/visualization/renderer_contract.py) 将上述结果封装为浏览器可消费的 payload，其中 `requested` 恒为 `true`，`spec` 是完整、已序列化的 `ChartSpec`，`echarts` 为确定性生成的 option 或 `null`。当不生成 ECharts option 时，`reason` 分别为 `table_requested`、`kpi_requested` 或 `not_chartable`。

## 七、当前代码的真实运行状态

Chart 契约、验证器和 payload 构造器已经存在，但尚未接入聊天事件的执行路径。当前链路如下：

```text
采购分析 Agent
  -> execute 输出普通文本或 chart NDJSON
  -> ToolMessage
  -> ChatService._semantic_message_events()
  -> tool_call_end.data.result（原始 stdout）
  -> 主 Agent 在最终回复中原样保留 chart JSON
```

[`chat_service.py`](../../src/api_view/chat_service.py) 的测试明确验证：即使 `execute` 输出有效 chart 文档，事件仍只有 `tool_call_end`，其 `data.result` 等于原始 stdout；无效 chart 文档也同样作为普通工具结果返回。与此同时，`parse_chart_documents()` 和 `build_chart_payload()` 在当前 `src` 中只有定义和导出，没有被 `ChatService`、历史消息接口或其他生产调用方使用。

这意味着下列说法在当前版本并不成立：

1. 后端会在 `execute` 返回时自动校验 chart JSON。
2. SSE 会发送独立的已验证图表 payload。
3. 历史消息接口会返回可直接渲染的 `echarts` 字段。

技能与主 Agent 提示词通过“完整 JSON 原样返回”维持了可用约定，但真正的服务端受控渲染链路仍需接线。记录这一差异很重要：文档不能把尚未调用的校验器当成线上保护措施。

## 八、采购分析中如何选择图表

图表应该服务已有 Motorparts 数据，而不是为了可视化而构造维度。

| 问题 | 合适类型 | 最小数据条件 | 不适合时的处理 |
| --- | --- | --- | --- |
| 同物料的供应商均价比较 | `bar` | 供应商名称与平均单价 | 样本过少时用 `table` 或文字 |
| 历史采购价格变化 | `line` | 有序日期与价格，且时间字段可比较 | 日期缺失时只输出汇总 |
| 成本或订单金额构成 | `pie` | 少量、互斥的类别与金额 | 类别过多时改 `bar` 或 `table` |
| 供应商评分、交期、价格明细 | `table` | 多字段明细行 | 不输出不受支持的 `radar`、`boxplot` |
| 总采购额、最低价、库存预警数量 | `kpi` | 可解释的单项聚合指标 | 说明样本和口径 |

`provenance` 必须列出实际调用的数据工具，例如 `supplier_query`、`part_by_supplier`、`order_search_details` 或 `inventory_warning`。数据不足、时间范围缺失、样本量过小等事实应写入 `warnings`，不能用模型猜测补齐。

## 九、接入受控渲染时的最小改动

若要让现有 `visualization` 包真正成为 SSE 与历史 API 的数据边界，建议按以下顺序接入：

1. 在接收 `execute` 的 `ToolMessage` 时调用 `parse_chart_documents(stdout)`；普通 stdout 保持原行为。
2. 对每个 `ChartSpec` 调用 `build_chart_payload()`，在事件中增加明确的 chart 字段或独立事件；不要把模型提供的 ECharts option 透传到浏览器。
3. 对 `ChartDocumentError` 返回可读的工具错误或受控警告，使 Agent 能根据 `chart_params.md` 修正输出，而不是静默渲染失败。
4. 为历史消息序列化同样保存或重建 chart payload，保证刷新页面后的展示和流式展示一致。
5. 补充覆盖多图表、`table`/`kpi`、`chartable=false`、行数超限和 chart JSON 混入普通日志的测试。

在完成这些改动前，前端若要从最终回复识别 chart JSON，必须把它视作未经过后端验证的 Agent 文本，而不是 `renderer_contract` 已保证安全的 payload。

## 十、常见错误

| 错误 | 后果 | 正确做法 |
| --- | --- | --- |
| 输出 Markdown 代码块或 `chart = {...}` | 逐行 JSON 解析器不会识别为图表文档 | 直接打印一整行 JSON |
| 输出 ECharts option | 越过受控的 schema 与转换器 | 只输出 `ChartSpec` 允许的字段 |
| `bar`/`line`/`pie` 缺少 `x`、`y` | 校验失败 | 将字段名写入 `x`、`y`，并确保每行都有对应键 |
| 在图表中附带报告、路径或状态 | 职责混乱，可能泄露内部信息 | chart 仅传数据；报告另行写入和读取 |
| 生成 PNG、SVG、PDF、HTML 文件 | 引入文件生命周期与展示安全问题 | 使用结构化 chart JSON |
| 主 Agent 转述、翻译或格式化 chart JSON | 多 Agent 交接后 JSON 不再可解析或语义被改变 | 最终回复原样保留完整 JSON |
| 将无效 chart 当作已验证数据渲染 | 当前代码不会自动阻止 | 先接入 `parse_chart_documents()` 与 payload 构造器 |

> 一句话结论：当前 Chart 设计的核心不是让模型“画图”，而是让它提交受限的数据规格；schema 和 ECharts 转换器已经准备好，下一步是把它们接入 `execute` 的事件和历史消息路径，形成真正可验证的端到端图表链路。
