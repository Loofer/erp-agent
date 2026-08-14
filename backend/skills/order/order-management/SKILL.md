---
name: order-management
description: >
  采购订单创建与更新主技能包。完成订单业务信息收集、字段校验、组装合规订单payload，输出交由外部系统处理审批与Motorparts写入。
---

# 采购订单管理技能（操作手册）

## 适用场景
- **创建采购订单**：收集订单头信息与采购明细，组装新建订单报文。
- **更新采购订单**：确认目标订单，收集变更字段，组装更新订单报文。

> 说明：审批、Motorparts写入属于外部系统能力，本Skill仅负责AI侧信息收集、校验、payload组装，不实现审批逻辑，不直接调用Motorparts。

## 核心执行流程

### 第 1 步：需求理解与信息收集
- **创建订单**：从对话提取订单编号、物料、数量、单价等业务信息，构建内部草稿`order_draft`。
- **更新订单**：优先确认目标订单主键`id`，缺失则触发追问；收集用户明确要求修改的字段；若修改采购明细，需要收集完整最新明细数组，不支持局部patch。

### 第 2 步：字段校验与追问补全
对照【字段规则速查】校验当前`order_draft`：
1. 校验**阻断字段**：识别缺失、格式非法的阻断字段，生成`missing_fields`嵌套字段路径数组。
2. 触发追问：存在不合规阻断字段时调用`request_order_info`
   - `missing_fields`仅填入阻断字段路径，示例：`["orderDetail[0].quantity"]`
   - `message`输出业务友好中文提示，一次性补全全部缺失项，禁止暴露底层字段路径给用户。
3. 循环补全：接收`human_response`增量合并更新`order_draft`，重复校验步骤，直到全部阻断字段合法。

> 工具约束：`missing_fields`为空时，禁止调用`request_order_info`。

### 第 3 步：组装 Payload，输出报文
1. **数据清洗**
   - 无业务值的可选字段直接移除key，禁止传递`null`；空字符串`""`视为无业务值一并剔除。
   - 全部剔除【禁止传入字段】列表内字段。
2. 生成`order_payload`输出交给外部系统执行后续调用。
3. **话术约束**：仅输出提交审批类提示；**审批通过且Motorparts返回成功前，严禁告知用户订单已创建/已更新/写入Motorparts**。

## 字段规则速查

### 1. 业务收集字段
| 业务信息 | 请求字段 | 校验规则与格式要求 | 缺失时处理策略 |
|---|---|---|---|
| 订单编号 | `orderNumber` | 非空字符串 | **阻断并追问** |
| 采购明细 | `orderDetail` | 数组，至少1条明细，不能为`null`/空数组 | **阻断并追问** |
| 采购物料 | `orderDetail[].partId` | 每条明细物料ID非空 | **阻断并追问** |
| 采购数量 | `orderDetail[].quantity` | ≥1整数；小数、0、负数需要追问修正 | **阻断并追问** |
| 采购单价 | `orderDetail[].unitPrice` | 有效数值 | **阻断并追问** |
| 下单时间 | `orderTime` | ISO‑8601 date‑time，例`2026‑08‑07T10:00:00Z` | 不阻断，不追问 |
| 预计交货日期 | `expectedDeliveryDate` | `yyyy‑MM‑dd` | 不阻断，不追问 |
| 创建人 | `createdBy` | Motorparts用户ID | 不阻断，不追问 |
| 订单备注 | `remark` | 业务文本备注 | 不阻断，不追问 |

> 格式处理：用户传入非标准时间格式，引导用户修正；禁止AI静默自动转换时间格式。

### 2. 禁止传入字段（系统维护 / 后端计算）
严禁写入`order_payload`：
- 主键与时间戳：`createTime`、`updateTime`、`orderId`
- 状态与自动计算：`status`、`totalAmount`、`orderDetail[].subtotal`
- 交付回填、查询字段：`actualDeliveryDate`、`partDetail`

> 备注：更新订单的目标主键`id`由外部系统作为独立入参处理，不放入payload。

## AI禁止行为
- 禁止自动生成`orderNumber`、`partId`业务主键，禁止自动填充默认值绕过信息收集。
- 禁止校验订单编号唯一性，唯一性交由下游系统处理。
- 禁止把底层嵌套字段路径直接展示给终端用户。

## 用户终止与异常
1. 用户明确放弃创建/更新：清空`order_draft`，结束流程。
2. 审批驳回、Motorparts报错属于外部系统事件，本Skill不修改本地`order_draft`，由外部系统完成用户提示。

## 对客话术参考

| 当前阶段 | ✅ 允许话术 | ❌ 禁止话术 |
|---|---|---|
| 信息收集中 | “还缺少XX信息，请帮我补充。” | “订单已创建。” |
| payload已输出，待外部审批 | “订单信息已整理完成，已提交审批流程。” | “订单已写入Motorparts。” |
| 审批被拒（外部返回） | “审批未通过，请修改信息后重新提交。” | “订单创建失败。” |
| 审批+Motorparts全部成功（外部返回） | “订单已成功创建并写入Motorparts。” | - |

## Payload示例

### 创建订单 payload
```json
{
  "orderNumber": "PO20260807001",
  "orderTime": "2026-08-07T10:00:00Z",
  "expectedDeliveryDate": "2026-08-20",
  "createdBy": 1001,
  "remark": "第一批物料采购",
  "orderDetail": [
    {
      "partId": 2001,
      "quantity": 10,
      "unitPrice": 1200.0
    }
  ]
}
```

### request_order_info工具入参示例
```json
{
  "order_draft": {
    "orderNumber": "PO20260807001",
    "orderDetail": [{"partId":2001}]
  },
  "missing_fields": ["orderDetail[0].quantity","orderDetail[0].unitPrice"],
  "message": "请补充第一条采购物料的采购数量和采购单价。"
}
```

### 更新订单 payload
```json
{
  "expectedDeliveryDate": "2026-09-01",
  "orderDetail": [
    {
      "partId": 2001,
      "quantity": 20,
      "unitPrice": 1200.0
    }
  ]
}
```