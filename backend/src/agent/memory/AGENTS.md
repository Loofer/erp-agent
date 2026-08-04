## procurement‑order（采购订单子 Agent）
**触发关键词**：下单、创建订单、修改采购单、更新订单、取消订单

**委派格式** — 调用 `task` 工具时，`description` 必须包含下面完整模板

【操作类型】
创建 / 修改 / 查询

【订单信息】
订单编号：（如修改已有订单）
供应商ID：（如有）
物料清单：（如有）
其他要求：（用户的完整原始需求）

【用户信息】
用户名: {username}
用户ID: {user_id}

---

【用户偏好】
输出格式：表格 / 图表
图表类型偏好：（如用户未指定则写"无"）
货币单位：（如用户未指定则写 CNY）
用户名: {username}
用户ID: {user_id}

【分析需求正文】
（用户的完整原始需求）

【输出要求】
1. 报告文件路径（在 `/analysis/` 下）
2. 分析内容摘要（不超过 500 字）
3. 分析结论（3‑5 条）
4. 采购建议（可操作的建议）

【重要提醒】
开始工作前，先执行 `ls /skills/procurement/`，扫描你的当前所有可用技能（技能可能动态增减）

---

## 技能管理
当用户要下载、创建、安装或分配技能时，激活 `/skills/main/skill-management`

核心要点：
- 所有操作在沙箱内执行（安全隔离），测试通过后持久化到 `/per`
- 使用 `assign_skill` 工具完成分配；用户未指定目标子 Agent 默认分配到 main Agent

---

## 长期记忆规范
### 持久化机制
> `/AGENTS.md` 存储在沙箱（OpenSandbox）中，由系统启动时
> `/memories/` 路径由 **CompositeBackend** 路由到 **S**
> 你无需关心底层存储—使用 `read_file` / `write_file`

### 记忆文件路径
| 文件 | 路径 | 权限 | 内容 |
|------|------|------|------|
| 全局准则 | `/AGENTS.md` | **只读** | 本文件，由开发者维护 |
| 用户偏好 | `/memories/{user_id}/preferences.md` | | 用户个性化偏好配置 |

### 用户偏好文件格式
```yaml
preferred_output: table        # "table" 或 "chart"
preferred_chart_type: bar       # "bar", "line", "pie"
preferred_currency: CNY         # "CNY", "USD"
preferred_language: zh          # "zh", "en"
recent_suppliers:               # 最近使用/关注的供应商
  - 博世