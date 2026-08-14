# 文件权限

> 文件权限控制的是 Deep Agents 内置文件工具的读写边界；它不是 Shell 沙箱，也不是自定义工具或 MCP 工具的通用安全策略。

## 一、项目配置

主 Agent 在 [`main_agent.py`](../../src/agent/main_agent.py) 中传入
`build_runtime_permissions()`。当前规则位于
[`runtime.py`](../../src/agent/memory/runtime.py)：

```python
FilesystemPermission(
    operations=["write"],
    paths=["/memory/**", "/skills/**"],
    mode="deny",
)
FilesystemPermission(
    operations=["read", "write"],
    paths=["/memories/**"],
    mode="allow",
)
```

这表达了三条业务边界：共享规则只读、共享技能只读、用户长期记忆可读写。当前实现没有追加全局 `/**` deny，因此未命中规则的路径仍按 Deep Agents 默认行为处理；新增路由时必须重新评估是否需要白名单策略。

## 二、规则匹配

`FilesystemPermission` 的字段含义：

| 字段 | 作用 |
| --- | --- |
| `operations` | `read` 覆盖 `ls`、`read_file`、`glob`、`grep`；`write` 覆盖 `write_file`、`edit_file`、`delete` |
| `paths` | Agent 看到的虚拟路径 Glob，例如 `/memories/**` |
| `mode` | `allow` 放行、`deny` 拒绝、`interrupt` 暂停等待人工决定 |

规则按声明顺序匹配，首条同时匹配操作和路径的规则生效；没有命中时默认允许。因此“只允许 `/workspace/**`”必须再增加末尾的全局拒绝，否则工作区之外仍可能被访问。

权限匹配的是虚拟路径，不是宿主机绝对路径。`/memory/`、`/memories/` 等路径先由 `CompositeBackend` 路由，再由权限中间件检查，二者职责不同：Backend 决定数据去哪，Permission 决定内置文件工具能否执行。

## 三、权限不覆盖的入口

以下入口需要单独治理：

| 入口 | 控制方式 |
| --- | --- |
| 自定义 LangChain 工具 | 工具自身校验、Middleware 或 `interrupt_on` |
| MCP 文件工具 | MCP Server 权限和工具审批 |
| `LocalShellBackend` / AIO Sandbox 的 `execute` | 沙箱隔离、命令策略、网络和凭证控制 |
| 依赖文件内容、用户身份或配额的动态规则 | Backend Policy Hook / `PolicyWrapper` |

禁止 `write_file` 写入某目录，并不等于禁止 Agent 通过 Shell 或自定义上传工具接触该目录。

## 四、记忆相关策略

- `/memory/AGENTS.md` 是开发者维护的共享规则，禁止 Agent 写入。
- `/skills/**` 是版本化技能说明，禁止 Agent 修改。
- `/memories/**` 是按 `(agent_id, user_id, "memories")` 隔离的用户记忆，允许读写。
- 涉及组织策略、合规文件或敏感信息时，建议改为应用预置、Agent 只读；需要人工确认的写入可使用 `interrupt`。

## 五、验证清单

- 允许读写 `/memories/preferences.md`。
- 写入或编辑 `/memory/**`、`/skills/**` 被拒绝。
- 删除受保护目录不会绕过写权限。
- 未命中规则的路径行为符合明确的默认策略。
- 自定义工具、MCP 和 `execute` 都有独立的安全检查。
