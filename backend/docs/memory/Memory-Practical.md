# 记忆与运行时隔离

> Deep Agents 的记忆不是“把所有历史消息塞进 Prompt”，而是把不同生命周期、不同可信度和不同访问范围的信息分层保存，再通过虚拟路径、Store namespace 和请求上下文组合到一次运行中。

## 一、先建立记忆分层

| 层级 | 解决的问题 | 本项目内容 | 生命周期 |
| --- | --- | --- | --- |
| 请求上下文 | 这一次请求是谁、什么时候、有哪些检索结果 | `user_id`、`username`、`agent_id`、`current_time`、`retrieval_context` | 单次调用 |
| 线程状态 | 当前对话如何继续 | 消息、工具调用、审批中断、图状态 | 同一 `thread_id` |
| 用户长期记忆 | 跨对话保留哪些用户偏好 | `/memories/preferences.md` | 跨线程、按用户持久化 |
| 共享运行规则 | Agent 必须遵守什么流程 | `/memory/AGENTS.md`、`prompts.py` | 随代码发布 |
| 技能与工具能力 | 如何执行特定领域任务 | `/skills/` 和注册工具 | 随版本发布 |

最容易混淆的是线程状态和长期记忆：checkpointer 让 Agent 在同一线程恢复上下文；StoreBackend 才让文件跨线程保留。长期记忆也不能替代 Motorparts 工具，当前库存、订单状态和价格必须以工具实时返回为准。

## 二、当前项目的记忆入口

`src/agent/main_agent.py` 创建主 Agent 时声明：

```python
deepagents.create_deep_agent(
    model=model,
    system_prompt=build_system_prompt(),
    memory=["/memory/AGENTS.md", "/memories/preferences.md"],
    backend=build_agent_backend(store=store),
    permissions=build_runtime_permissions(),
    context_schema=MemoryContext,
)
```

`memory` 是启动时加载的文件路径清单：共享规则提供稳定约束，偏好文件提供用户可复用的长期信息。路径本身不决定存储位置，`CompositeBackend` 负责路由，`FilesystemPermission` 负责读写边界。

## 三、记忆文件与存储后端

`/memory/AGENTS.md` 和 `prompts.py` 是随代码发布的共享规则，运行时只读；`/memories/preferences.md` 是用户长期偏好文件，由 `StoreBackend` 保存。权限和所有虚拟路径的完整说明见 [`文件权限.md`](Filesystem-Permission-Practical.md)；Shell 执行环境和 AIO Sandbox 迁移见 [`沙箱.md`](Sandbox-Practical.md)。

### `/memories/`：用户长期记忆

`/memories/preferences.md` 保存用户明确表达、未来有用且不敏感的偏好，例如：

```yaml
preferred_output: table
preferred_chart_type: bar
preferred_currency: CNY
preferred_language: zh
recent_suppliers:
  - 博世
```

Agent 通过普通文件工具读写该路径；底层由 `StoreBackend` 保存。生产环境的 `store` 来自 PostgreSQL，测试可以注入 `InMemoryStore`。后者重启即丢失，只适合开发和测试。

## 四、谁能看到哪份长期记忆

命名空间函数 `assistant_memory_namespace()` 从运行时上下文读取 `agent_id` 和 `user_id`，返回：

```python
(agent_id, user_id, "memories")
```

这形成清晰的隔离关系：

```text
同一 Agent + 同一用户       不同线程可共享偏好
同一 Agent + 不同用户       相互隔离
不同 Agent + 同一用户       相互隔离
```

两个 ID 必须匹配 `[A-Za-z0-9._@+:~-]+`。缺失、为空或包含路径分隔符时直接抛出 `ValueError`，不退化到公共 namespace。`username` 只用于显示，不参与隔离。

当前实现是“用户级记忆 + Agent 级隔离”，不是所有用户共享的 Agent 记忆。若未来加入组织级合规策略，应使用独立组织 namespace，由应用代码预置并设置为只读，避免把共享策略写进用户偏好文件。

## 五、一次请求如何使用记忆

```text
请求进入
  -> 组装 Runtime context
  -> 加载共享 /memory/AGENTS.md
  -> 按 namespace 加载 /memories/preferences.md
  -> middleware 生成请求级 system prompt
  -> Agent 执行工具、子 Agent 与审批流程
  -> 用户确认的新偏好写回 /memories/preferences.md
  -> checkpointer 保存本线程状态
```

`RequestContextPromptMiddleware` 调用 `build_request_system_prompt()`，将身份、当前时间和 RAG 结果加入本次模型请求。RAG 内容明确标记为不受信任的参考资料，只能支持答案并引用 `source_id`，不能覆盖 `/memory/AGENTS.md` 的规则，也不应被写入长期记忆。

## 六、什么时候应该更新长期记忆

适合写入：

- 用户明确说“记住我偏好表格输出”“以后使用中文”等稳定偏好。
- 用户确认的展示格式、币种、语言或常用供应商。
- 经过确认、未来多次对话确实会复用的工作习惯。

不应写入：

- 当前库存、价格、订单状态等实时 Motorparts 事实。
- 未经用户确认的模型推断或一次性任务细节。
- 密码、API Key、银行卡号等敏感凭据。
- RAG 返回的临时上下文或外部资料原文。

推荐更新流程：

1. 识别用户是否提出了明确、稳定的偏好。
2. 读取现有 `preferences.md`，保留未涉及的字段。
3. 只修改确认过的字段，避免覆盖其他偏好。
4. 写回 `/memories/preferences.md`，向用户说明已记录或无法记录。
5. 下一次新线程通过 `memory=` 自动读取验证效果。

示例：用户说“以后默认用表格展示”，Agent 应保留其他 YAML 字段，仅将 `preferred_output` 更新为 `table`，而不是重写整个文件。

## 七、并发、整理与生产部署

同一文件的并发更新可能产生 last-write-wins。当前偏好文件写入频率低，但仍应在更新前读取最新内容并保留未知字段。高频场景可按主题拆文件，或先将对话事件追加到独立文件，再由后台整合任务去重合并；共享记忆应由后台任务串行写入，普通 Agent 只读。

生产服务应在应用生命周期中创建并释放 PostgreSQL Store；预置默认记忆时使用 Store 提供的结构化文件数据接口（如 `create_file_data`），不要手工拼接底层 JSON，并确保预置 namespace 与 `assistant_memory_namespace()` 完全一致。

## 八、验证清单

- 同一用户、同一 Agent 的不同线程能读取相同偏好。
- 不同用户或不同 Agent 不能读取彼此的偏好。
- 非法 `user_id`、`agent_id` 会被拒绝。
- RAG 内容进入请求提示词，但不能替换系统规则。
- Store 不可用时不伪造 Motorparts 事实，并能继续提供有限服务。

> 总结：用 checkpointer 保存“当前线程”，用 `/memories/` 保存“用户偏好”，用 `/memory/` 固化“共享规则”，再用 namespace 和权限把边界落实到运行时，Agent 才能跨对话记住有用信息而不发生数据串线。
