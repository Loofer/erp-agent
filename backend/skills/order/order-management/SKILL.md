---
name: order-management
description: 采购订单创建与更新。负责订单业务信息收集、人工审批和 ERP 写入流程。
---

# 采购订单管理 Skill

## 职责边界

本文件定义订单的业务信息收集规则。AI 根据这些规则检查草稿、识别需要向用户确认的信息并生成追问。`request_order_info` 只负责人工输入中断，不执行字段校验。

当 `missing_fields` 为空时，`request_order_info` 会直接返回 `status: complete`，不会触发人工中断。

## 写入约束

- `create_order` 和 `update_order` 均由官方 `HumanInTheLoopMiddleware` 在执行前拦截。
- 只有审批结果为 `approve` 时才会调用 ERP；`reject` 时不会执行写入。
- 在审批通过且 ERP 成功返回前，不能称订单已创建、已更新或已写入 ERP。
- 没有值的可选字段必须省略，不能传 `null`。
- 创建时不得传入后端维护的 `id`、`createTime`、`updateTime`、`orderId` 或查询专用的 `partDetail`。

## 创建订单的业务信息

接口层只强制 `orderNumber`，但创建一张可执行的采购订单时，AI 必须按以下业务层规则收集信息。

### 必须确认

缺少以下任一信息时，AI 必须通过 `request_order_info` 向用户追问，不能进入审批：

| 业务信息 | 请求字段 | 规则 |
| --- | --- | --- |
| 订单编号 | `orderNumber` | 非空且能区分该订单 |
| 采购明细 | `orderDetail` | 至少一条明细 |
| 采购物料 | `orderDetail[].partId` | 每条明细必须指定物料 ID |
| 采购数量 | `orderDetail[].quantity` | 每条明细必须为大于等于 1 的整数 |
| 采购单价 | `orderDetail[].unitPrice` | 每条明细必须提供单价 |

### 推荐确认

以下信息不阻塞创建；已知时应带入订单，未知时可由用户确认后省略：

| 业务信息 | 请求字段 | 建议 |
| --- | --- | --- |
| 下单时间 | `orderTime` | 记录实际下单时间，使用 ISO-8601 date-time |
| 预计交货日期 | `expectedDeliveryDate` | 用于到货计划，格式为 `yyyy-MM-dd` |
| 创建人 | `createdBy` | 已知 ERP 用户 ID 时记录 |
| 订单备注 | `remark` | 记录紧急程度、交货要求等业务说明 |

### 自动计算、交付后补充或系统维护

- `totalAmount` 和明细的 `subtotal` 可由后端计算；用户未明确提供时不应追问，也不要传 `null`。
- `actualDeliveryDate` 只在实际交付后补充；创建订单时不应追问，也不要传 `null`。
- `status` 由系统维护；AI 不向用户索取，也不主动传入。

## 草稿补充流程

1. 维护当前 `order_draft`，只对“必须确认”信息检查缺失或不合法值。
2. 对缺失项生成字段路径，例如 `orderNumber`、`orderDetail[0].quantity`。
3. 调用 `request_order_info`，传入当前 `order_draft`、`missing_fields` 和明确的中文追问 `message`。
4. 从 `human_response` 提取用户补充内容，增量合并到原草稿。推荐确认信息在用户提供时合并，但其缺失不应阻塞流程。
5. 必须确认信息完整后，准备 `order_payload` 调用 `create_order`。

## 更新订单

更新时，先确认 `order_id`。涉及采购明细时仍按“必须确认”规则收集完整明细；其他字段按用户明确要求更新。准备好 `order_payload` 后调用 `update_order`，审批通过才会 `PUT /api/orders/update/{id}`。

## 创建示例

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
