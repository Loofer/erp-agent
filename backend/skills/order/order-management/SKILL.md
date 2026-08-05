---
name: order-management
description: 采购订单管理能力，支持采购订单创建、订单更新全流程处理；草稿字段补齐后执行人工审批流程，审批未完成严禁告知用户订单已写入ERP系统，禁止伪造订单生效状态。
---

# 采购订单管理 Skill

## 能力总览
本Skill处理采购订单的**创建**与**更新**业务流程，严格遵循字段校验‑信息收集‑人工审批‑ERP落库的完整链路。
> 核心铁则：**人工审批完成之前，绝对不对外宣称订单已经创建、更新或者写入ERP；审批拒绝时不会执行任何ERP写入动作。**

> 接口说明：创建采购订单接口主体包含三层结构：订单主表、orderDetail订单明细数组、partDetail物料详情对象。
> - `partDetail`：查询返回用于展示物料档案，**创建/更新订单入参不需要完整传入，仅传递partId引用物料档案即可**。
> - `id/createTime/updateTime/orderId`：后端自动生成维护，调用接口时禁止传入。
> - `deleted`：逻辑删除标记，业务新建固定传`0`。

## 字段约束说明
### 订单主表（创建接口入参）
| 字段 | 类型 | 是否入参必填 | 说明 |
|---|---|---|---|
| deleted | number | 是 | 逻辑删除标记，新建固定传0 |
| id | number | ❌禁止传入 | 订单主键ID，后端生成 |
| createTime | string | ❌禁止传入 | UTC创建时间，后端维护 |
| updateTime | string | ❌禁止传入 | UTC更新时间，后端维护 |
| orderNumber | string | ✅必填 | 采购订单业务编号 |
| totalAmount | number | 可选 | 订单总金额，明细subtotal求和，可后端自动计算 |
| status | number | ✅必填 | 订单状态编码，0=草稿/待审批，业务枚举 |
| orderTime | string | ✅必填 | 下单业务时间，ISO‑8601 UTC格式 `yyyy‑MM‑ddTHH:mm:ss.SSSZ` |
| expectedDeliveryDate | string | ✅必填 | 预计交货日期，纯日期格式`yyyy‑MM‑dd` |
| actualDeliveryDate | string | 可选 | 实际交货日期；新建订单传null，交付后回填 |
| createdBy | number | ✅必填 | 创建人用户ID |
| remark | string | 可选 | 订单整体备注 |
| orderDetail | array | ✅必填 | 订单明细数组，至少包含1条明细 |

### orderDetail 订单明细（数组子项）
| 字段 | 类型 | 是否入参必填 | 说明 |
|---|---|---|---|
| deleted | number | 是 | 明细逻辑删除标记，新建固定传0 |
| id | number | ❌禁止传入 | 明细行主键ID，后端生成 |
| createTime | string | ❌禁止传入 | 明细创建时间，后端维护 |
| updateTime | string | ❌禁止传入 | 明细更新时间，后端维护 |
| orderId | number | ❌禁止传入 | 关联主订单ID，后端回填 |
| partId | number | ✅必填 | 物料档案主键ID，关联物料 |
| quantity | number | ✅必填 | 采购数量 |
| unitPrice | number | ✅必填 | 物料采购单价 |
| subtotal | number | 可选 | 行小计=quantity*unitPrice，可后端计算 |
| remark | string | 可选 | 明细行备注 |
| partDetail | object | ❌无需传入 | 物料档案详情，仅查询返回展示 |

### partDetail 物料详情对象
> 仅查询订单接口返回，**创建、更新订单请求禁止传入该对象**，依靠partId关联物料档案。

## 订单创建流程
1. 发起新建采购订单，首先校验草稿必填字段完整性。
> 必填校验清单：主表`orderNumber、status、orderTime、expectedDeliveryDate、createdBy`；orderDetail数组不为空，每条明细`partId、quantity、unitPrice`不为空。
3. 草稿全部必填字段补齐后，调用 `create_order`，传入完整订单主体数据以及 `orderDetail` 明细数据。
4. `create_order` 调用会触发 Deep Agents 人工审批中断：
   - 审批结果为 `approve（批准）`：才会执行 ERP 请求 `POST /api/orders/create`，正式落库。
   - 审批结果为 `reject（拒绝）`：不会向ERP发起创建请求，订单不会落库。
5. 审批周期内，禁止向用户反馈“订单已创建”“已存入ERP”等表述，仅告知用户当前处于人工审批阶段。

## 订单更新流程
1. 更新采购订单，首先确认**订单ID**以及全部待更新业务数据，校验更新所需字段完整性。
> 更新必填校验：`order_id`必须提供；更新携带的业务字段同样遵循上面字段约束，明细行必填项与创建保持一致。
2. 字段校验通过，调用 `update_order(order_id, order)`，触发 Deep Agents 人工审批中断。
   - 审批结果为 `approve（批准）`：执行ERP接口 `PUT /api/orders/update/{id}`，完成订单更新落库。
   - 审批结果为 `reject（拒绝）`：不执行ERP更新接口，订单无变更。
3审批过程中，不得告知用户订单已经修改、已经同步至ERP。

## 通用约束与兜底规则
1. 所有ERP实际写入动作，**必须以人工审批通过为前置条件**，审批拒绝直接终止流程，不调用后端ERP接口。
2. 审批进行中，对外状态描述如实说明：订单待人工审批，尚未写入ERP，不虚构订单生效状态。
3. 仅当收到审批通过的返回结果，且ERP接口调用成功后，才可告知用户订单创建/更新完成。
4. 禁止传入后端自维护字段：`id、createTime、updateTime、orderId`，传入会被后端覆盖。
5. 创建更新请求不要携带`partDetail`完整对象，仅通过`partId`引用物料档案。
6. 可基于业务后续扩展：增加撤销、查询、作废订单等子流程，保持“审批‑落库”约束逻辑一致。

## 最简创建入参示例（参考）
```json
{
  "deleted": 0,
  "orderNumber": "PO20260804001",
  "totalAmount": 1200,
  "status": 0,
  "orderTime": "2026-08-04T08:24:50.065Z",
  "expectedDeliveryDate": "2026-08-15",
  "actualDeliveryDate": null,
  "createdBy": 1001,
  "remark": "测试采购订单",
  "orderDetail": [
    {
      "deleted": 0,
      "partId": 2001,
      "quantity": 2,
      "unitPrice": 600,
      "subtotal": 1200,
      "remark": "物料备注"
    }
  ]
}