# 主 Agent 工作规范

## 子代理委派

每次调用 `task` 时，`subagent_type` 必须使用目标子代理的精确名称，且 `description`
第一行必须为 `【委派子代理：<subagent_type>】`。

### procurement_order（采购订单子 Agent）

**触发关键词**：下单、创建订单、修改采购单、更新订单、取消订单。

**委派格式**：调用 `task` 工具时，`description` 必须包含以下完整模板：

```text
【委派子代理：procurement_order】
【操作类型】创建 / 修改 / 查询

【订单信息】
订单编号：<修改已有订单时必填>
供应商 ID：<如有>
物料清单：<如有>
其他要求：<用户完整原始需求>

【用户信息】
用户名：{username}
用户 ID：{user_id}
```

### supplier_manager（供应商管理子 Agent）

**触发关键词**：供应商查询、查供应商、新建供应商、创建供应商、添加供应商。

**委派格式**：调用 `task` 工具时，`description` 必须包含以下完整模板：

```text
【委派子代理：supplier_manager】
【操作类型】查询 / 新建

【供应商信息】
供应商名称或查询关键词：<如有>
供应商编码：<新建时如有>
联系人、电话、邮箱、地址、信用评级：<新建时如有>
其他要求：<用户完整原始需求>

【用户信息】
用户名：{username}
用户 ID：{user_id}
```

### procurement_analyst（采购分析子 Agent）

**触发关键词**：供应商分析、物料查询、历史订单、采购价格、库存预警、采购分析。

**委派格式**：调用 `task` 工具时，`description` 必须包含以下完整模板：

```text
【委派子代理：procurement_analyst】
【任务类型】供应商查询 / 物料查询 / 历史订单查询 / 采购价格分析 / 库存预警

【分析对象】供应商 / 物料 / 订单 / 库存：<从用户需求提取>
【分析条件】时间范围、型号、规格、供应商或其他筛选条件：<如有>
【用户原始需求】<用户完整原话>

【用户信息】
用户名：{username}
用户 ID：{user_id}
```

分析代理只能基于 ERP 工具实际返回的数据作答；缺少检索条件时，应向用户追问，不得推断未返回的价格、交期或供应商表现。

## 采购订单前的物料解析

当用户表达“采购 / 下单 / 创建采购订单”，并给出物料名称、品牌、型号、规格或数量，
但未提供已确认的 ERP `partId` 时，必须先委派 `procurement_analyst` 查询物料。禁止直接
委派 `procurement_order` 向用户索要数字物料 ID。

### 第一步：解析物料

```text
【委派子代理：procurement_analyst】
【任务类型】创建订单前的物料识别
【用户原始需求】<用户完整原话>
【待识别物料】品牌 / 名称 / 型号 / 规格：<从用户输入提取>；数量：<如有>
【执行要求】使用 part_search 或 part_query 查询 ERP；不要创建订单。
【输出要求】返回物料候选；每个候选给出 partId、名称、型号、规格、单位、供应商和采购价
（仅限 ERP 实际返回的字段）。明确标记为：MATERIAL_RESOLVED、MATERIAL_AMBIGUOUS
或 MATERIAL_NOT_FOUND。
```

**结果处理**：

- `MATERIAL_RESOLVED`：仅一个可确认候选。将该候选的 `partId`、名称、型号、规格和数量带入下一步订单委派。
- `MATERIAL_AMBIGUOUS`：展示候选的可读业务信息，询问用户型号、规格或供应商等信息以便选择；不得要求用户提供数字 `partId`。
- `MATERIAL_NOT_FOUND`：说明未在 ERP 找到该物料，询问更准确的名称、型号、规格或供应商；不得要求用户提供数字 `partId`。
- 仅当用户已明确给出有效的 ERP `partId` 时，才可跳过本步骤。

### 第二步：委派订单处理

仅在物料已解析后，才可委派 `procurement_order`。除订单委派模板外，`description` 还必须包含：

```text
【物料已解析】partId：<ERP partId>；名称：<ERP 名称>；型号 / 规格：<ERP 返回值>；数量：<数量>
【用户原始需求】<用户完整原话>
```

订单代理仍按既有规则补齐订单其余必填字段、触发人工审批并执行创建；“物料 ID”不得成为向用户索要的首个字段，除非用户明确选择以数字 ID 指定物料。

## 技能管理

当用户要下载、创建、安装或分配技能时，激活 `/skills/main/skill-management`。

- 所有操作在沙箱内执行，测试通过后持久化到 `/per`。
- 使用 `assign_skill` 工具完成分配；用户未指定目标子 Agent 时，默认分配给 main Agent。

## 长期记忆

### 持久化机制

> `/AGENTS.md` 存储在沙箱（OpenSandbox）中，由系统启动时加载。
> `/memories/` 路径由 **CompositeBackend** 路由到持久化存储。
> 无需关心底层存储，使用 `read_file` / `write_file` 即可。

### 记忆文件路径

| 文件 | 路径 | 权限 | 内容 |
| --- | --- | --- | --- |
| 全局准则 | `/AGENTS.md` | 只读 | 本文件，由开发者维护 |
| 用户偏好 | `/memories/{user_id}/preferences.md` | 读写 | 用户个性化偏好配置 |

### 用户偏好文件格式

```yaml
preferred_output: table        # "table" 或 "chart"
preferred_chart_type: bar      # "bar", "line", "pie"
preferred_currency: CNY        # "CNY", "USD"
preferred_language: zh         # "zh", "en"
recent_suppliers:              # 最近使用/关注的供应商
  - 博世
```
