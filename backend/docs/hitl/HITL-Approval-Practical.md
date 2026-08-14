# Human-in-the-Loop：让 Motorparts 写操作在人工确认后才落库

> 在 Motorparts 场景中，Agent 能够整理采购订单或供应商资料，并不意味着它应当自行写入系统。Human-in-the-Loop（HITL）的职责是把“已生成可执行请求”和“真正发生业务变更”分开：人确认之前，创建或更新请求绝不能发送。

用户说“帮我创建供应商”，Agent 会提取并校验供应商资料；用户补齐字段后，它可以组装 `supplier_payload`，但 `create_supplier` 仍会在 HTTP 请求前暂停。采购订单的创建和更新同理。这个暂停点既避免了错误写入，也让操作者有机会检查即将提交的参数。

本文说明本项目已经落地的 HITL 链路，并以实际代码和前端行为为准。底层 HITL 还支持 `edit`、`respond` 等决策；当前 Motorparts 写操作只开放 `approve` 与 `reject`，具体边界见下文。

## 一、当前保护的操作

当前系统只对 Motorparts 状态变更设置审批；查询和草稿收集不会触发写入审批。

| 子代理 | 受保护工具 | 实际 HTTP 操作 | 允许决策 | 不需要审批的操作 |
| --- | --- | --- | --- | --- |
| `supplier_manager` | `create_supplier` | `POST /api/suppliers/create` | `approve`、`reject` | `search_suppliers`、补充供应商字段 |
| `procurement_order` | `create_order` | `POST /api/orders/create` | `approve`、`reject` | 补充订单字段 |
| `procurement_order` | `update_order` | `PUT /api/orders/update/{order_id}` | `approve`、`reject` | 无 |

这条边界很重要：审批针对的是会改变 Motorparts 状态的工具调用，不是针对用户的每一句输入，也不是用 RAG 或提示词替代权限校验。工具本身仍会对请求载荷做收敛处理，例如供应商创建仅保留 API 可写字段，订单工具会移除 `None` 值和只读信息。

## 二、两种“等人”的场景

项目把人工介入分成两个语义不同的中断，前端也据此采用不同交互。

| 类型 | 触发方式 | 人的作用 | 恢复数据 | 前端表现 |
| --- | --- | --- | --- | --- |
| 补充信息 | `request_order_info` / `request_supplier_info` 内部调用 `interrupt()` | 填补缺失或不合法字段 | 原始字符串 | 输入框继续可用，显示追问提示 |
| 审批写操作 | YAML 的 `interrupt_on` 交给 `HumanInTheLoopMiddleware` | 批准或拒绝一项待执行的工具调用 | `{"decisions": [...]}` | 展示工具参数，输入框替换为批准/取消按钮 |

不要混淆两者。`request_*_info` 是“向人取值”的工具，不调用 Motorparts；它在恢复后将用户输入作为 `human_response` 返回给 Agent。`create_*` 和 `update_order` 则是有副作用的工具，拒绝时应使用 `reject`，使模型明确知道该写操作没有发生。

```text
缺少字段：用户请求 -> request_*_info -> interrupt -> 用户补充 -> 合并草稿并重新校验

写操作：  校验通过 -> create_* / update_order -> interrupt_on -> 人工审批
          -> approve -> 调用 Motorparts HTTP API -> 返回结果
          -> reject  -> 工具不执行，Agent 说明未写入
```

## 三、配置是审批策略的唯一入口

子代理定义在 YAML 中声明工具及其审批策略，加载器会校验 `interrupt_on` 的结构，并将其传递给 Deep Agents 的 `SubAgent`。供应商创建的配置如下：

```yaml
# src/agent/subagents/configs/supplier_manager.yaml
tools:
  - request_supplier_info
  - create_supplier
  - search_suppliers
interrupt_on:
  create_supplier:
    allowed_decisions:
      - approve
      - reject
```

采购订单配置对两个写工具采用相同策略：

```yaml
# src/agent/subagents/configs/procurement_order.yaml
interrupt_on:
  create_order:
    allowed_decisions:
      - approve
      - reject
  update_order:
    allowed_decisions:
      - approve
      - reject
```

[`loader.py`](../../src/agent/subagents/loader.py) 会拒绝非映射类型的 `interrupt_on`、缺少 `allowed_decisions` 的配置，以及空工具名或空决策名。转换子代理时，`definition.interrupt_on` 被原样传入 `SubAgent`；Deep Agents 因而在工具调用前创建可持久化的审批中断。

> 新增写工具时，先将它列入对应子代理的 `tools`，再配置 `interrupt_on`。只在提示词中要求“先询问用户”不是可靠的安全控制，模型仍可能直接调用工具。

## 四、一次创建供应商如何经过系统

以下链路覆盖了从用户输入到 Motorparts 写入的完整责任划分：

```text
ChatView / Sender
    -> POST /api/chat/stream
    -> supplier_manager 子代理
    -> request_supplier_info（字段缺失时，原生 interrupt）
    -> create_supplier（字段完整时，HITL 审批中断）
    -> ChatService 转换为 interrupt SSE 事件
    -> InterruptCard + HitlApprovalBar
    -> POST /api/chat/{thread_id}/resume
    -> Command(resume={"decisions": [...]})
    -> create_supplier 的 HTTP POST
    -> 工具结果和最终回复
```

供应商和订单子代理的系统提示词还要求：调用创建/更新工具后只能说“已提交审批”；只有工具返回成功，才能告知用户数据已经写入 Motorparts。这样 Agent 的自然语言状态与实际副作用保持一致。

### 1. 原生输入中断保留草稿

[`hitl_tools.py`](../../src/agent/tools/hitl_tools.py) 中的 `request_supplier_info` 和 `request_order_info`，仅在 `missing_fields` 非空时调用 `langgraph.types.interrupt()`：

```python
human_response = interrupt(
    {
        "kind": "tool_input",
        "tool_name": "request_supplier_info",
        "message": message,
        "supplier_draft": dict(supplier_draft),
        "missing_fields": list(missing_fields),
    }
)
```

中断值同时带有当前草稿、缺失字段和面向用户的中文问题。恢复后工具返回原草稿、`missing_fields` 与 `human_response`，由子代理按对应 Skill 合并并重新校验，不能把未校验的用户文本直接发送给 API。

### 2. 审批中断发生在 HTTP 调用之前

[`suppliers_tools.py`](../../src/agent/tools/suppliers_tools.py) 的 `create_supplier` 和 [`orders_tools.py`](../../src/agent/tools/orders_tools.py) 的 `create_order`、`update_order` 是普通工具函数；它们本身不手写审批逻辑。审批由 YAML 产生的 `HumanInTheLoopMiddleware` 包裹，只有用户恢复为 `approve` 后，工具函数才会执行 `ApiClient.post()` 或 `ApiClient.put()`。

这种分层有两个结果：业务工具可以专注于参数收敛和 API 调用，审批策略仍集中在可审查、可测试的子代理配置中。

## 五、后端如何把 LangGraph 中断交给界面

[`chat_service.py`](../../src/api_view/chat_service.py) 以 `stream_mode=["messages", "values"]` 运行图。遇到 `values` 事件中的 `interrupts` 后，服务会：

1. 按 `Interrupt.id` 去重。子代理中断会沿子图命名空间向上重新发出，去重可避免界面重复出现同一个审批卡。
2. 继续消费流而不提前 `break`，保证 checkpoint 已记录待处理的中断；否则恢复时可能重放节点。
3. 调用 `_interrupt_data()`，发送 `interrupt` SSE 事件。事件包含 `thread_id`、`namespace`、工具名、参数、描述和每个操作允许的决策。

审批事件的核心数据形状如下：

```json
{
  "thread_id": "...",
  "interrupt_mode": "approval",
  "resume_mode": "decisions",
  "allowed_decisions": ["approve", "reject"],
  "actions": [
    {
      "name": "create_supplier",
      "args": { "supplier_payload": { "supplierCode": "S-100" } },
      "description": "Create a supplier after Deep Agents' required human approval.",
      "allowed_decisions": ["approve", "reject"]
    }
  ]
}
```

`_interrupt_data()` 会把原生 `{"kind": "tool_input", ...}` 标记为 `interrupt_mode="input"` 与 `resume_mode="value"`；Deep Agents 审批请求则标记为 `approval` 与 `decisions`。这是前端选择恢复数据格式的依据，不能只按工具名猜测。

## 六、前端如何展示与恢复

前端在 [`chat.ts`](../../../frontend/src/stores/chat.ts) 收到 SSE 的 `interrupt` 后，把它写入 `pendingInterrupt` 并追加一条中断消息。[`InterruptCard.vue`](../../../frontend/src/components/InterruptCard.vue) 会根据模式渲染内容：审批型中断以 JSON 展示工具、描述和参数，输入型中断展示 Agent 的补充信息提示。

[`ChatView.vue`](../../../frontend/src/views/ChatView.vue) 根据 `interrupt_mode` 切换底部区域：

| 模式 | 界面 | 恢复请求 |
| --- | --- | --- |
| `input` | 保留 Sender，显示追问提示，用户可继续输入缺失字段 | 原生工具中断直接提交文本 |
| `approval` | 隐藏 Sender，显示“批准执行”“取消操作” | 每个待审批 action 对应一条 `approve` 或 `reject` 决策 |

当前界面已提供“补充信息”和“审批写操作”两种交互。对于审批型写操作，[`HitlApprovalBar.vue`](../../../frontend/src/components/HitlApprovalBar.vue) 目前仅提供两个按钮。因此尽管底层 HITL 支持 `edit`、`respond` 等决策，当前 Motorparts 写操作的审批决策只有 `approve` 与 `reject`；这不影响 `request_*_info` 的自由文本补充。要开放编辑审批，必须同时更新 YAML 的 `allowed_decisions`、前端参数编辑界面和恢复载荷，不能只改其中一处。

恢复请求统一发送到：

```text
POST /api/chat/{thread_id}/resume
```

审批使用：

```json
{
  "resume": {
    "decisions": [{ "type": "approve" }]
  }
}
```

拒绝使用同样的结构，将 `type` 改为 `reject`。补充字段的原生工具中断则使用：

```json
{ "resume": "联系人电话为 13800138000" }
```

后端将 `resume` 原样传给 `Command(resume=resume_data)`，所以恢复必须使用创建中断时的同一 `thread_id`。Checkpoint 是恢复协议的一部分，不应把审批数据拼接成一条新的聊天消息。

## 七、新增一个需审批写工具的清单

以“删除采购订单”为例，完整改动至少应覆盖下列四项：

1. 在领域工具模块实现 `delete_order`，并限制入参与 API 可写范围；工具返回值必须能让 Agent 区分成功与失败。
2. 将工具名加入订单子代理 YAML 的 `tools`，并在 `interrupt_on` 中配置至少 `approve`、`reject`。
3. 在子代理提示词或关联 Skill 中明确：审批前不宣称已删除，拒绝后明确说明未执行。
4. 增加配置加载、暂停、批准恢复、拒绝不调用 HTTP API 的测试；必要时扩展前端卡片对新参数的脱敏或格式化。

不要将低风险查询工具加入审批，也不要绕过子代理直接在其他 Agent 中注册同一个写工具。前者会放大操作阻力，后者会在新的调用路径上失去保护。

## 八、验证与排障

建议按真实业务动作验证，而不只检查界面上出现了按钮：

| 检查点 | 预期结果 |
| --- | --- |
| 缺失供应商或订单字段 | 收到 `input` 中断；恢复文本后草稿会重新校验 |
| 字段完整但未审批 | 收到 `approval` 中断；Motorparts 不产生写请求 |
| 点击批准 | 使用原 `thread_id` 恢复；只执行对应的创建或更新工具一次 |
| 点击取消 | 发送 `reject`；Motorparts 不产生写请求，Agent 明确说明未写入 |
| 子代理中断冒泡 | 界面只显示一张审批卡，不因命名空间冒泡重复显示 |
| 重新启动或流结束后恢复 | checkpoint 中仍存在待处理的中断，可继续当前会话 |

后端已有针对配置加载、原生输入中断和聊天中断投影的测试。开发时可运行：

```powershell
cd backend
uv run pytest -v
uv run ruff check .
```

> 一句话结论：当前 HITL 不是“让 Agent 多问一句”，而是一条可恢复的执行闸门。草稿缺字段时，人提供信息；准备写 Motorparts 时，人决定是否放行；在 `approve` 到达前，副作用工具不应执行。
