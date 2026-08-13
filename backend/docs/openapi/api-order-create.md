# 接口文档：创建采购订单
## 接口基础信息
| 项 | 值 |
| ---- | ---- |
| 接口地址 | `/api/orders/create` |
| 请求方式 | `POST` |
| 接口标签 | 采购订单管理 |
| 接口摘要 | 创建采购订单 |
| operationId | create_2 |

> 请求头：`Content-Type: application/json`，请求体必传
>
> 创建请求只能在人工审批通过后发送。未提供值的可选字段必须省略，不能以
> `null` 传递；例如没有可用总金额时不要发送 `totalAmount`。

## 请求体
### 请求体模型：PurchaseOrderWithDetails
**必填字段**：`orderNumber`

| 字段名 | 类型 | 格式 | 是否必填 | 说明 |
|---|---|---|---|---|
| deleted | integer | int32 | 否 | 删除标记 |
| createTime | string | date‑time | 否 | 后端维护，创建时不得传入 |
| updateTime | string | date‑time | 否 | 后端维护，创建时不得传入 |
| id | integer | int64 | 否 | 后端生成，创建时不得传入 |
| orderNumber | string | - | ✅是 | 订单编号 |
| totalAmount | number | - | 否 | 订单总金额；无值时省略，不能传 `null` |
| status | integer | int32 | 否 | 订单状态 |
| orderTime | string | date‑time | 否 | 下单时间 |
| expectedDeliveryDate | string | date | 否 | 预计交货日期 |
| actualDeliveryDate | string | date | 否 | 实际交货日期；无值时省略，不能传 `null` |
| createdBy | integer | int64 | 否 | 创建人ID |
| remark | string | - | 否 | 订单备注 |
| orderDetail | array | - | 否 | 订单明细数组，数组项：`OrderDetailWithPart` |

#### 子模型：OrderDetailWithPart（orderDetail数组内元素）
**必填字段**：`partId`、`quantity`、`unitPrice`

| 字段名 | 类型 | 格式 | 是否必填 | 说明 |
|---|---|---|---|---|
| deleted | integer | int32 | 否 | 删除标记 |
| createTime | string | date‑time | 否 | 后端维护，创建时不得传入 |
| updateTime | string | date‑time | 否 | 后端维护，创建时不得传入 |
| id | integer | int64 | 否 | 后端生成，创建时不得传入 |
| orderId | integer | int64 | 否 | 创建时由后端关联，不得传入 |
| partId | integer | int64 | ✅是 | 配件ID |
| quantity | integer | int32 | ✅是 | 采购数量，最小值：1 |
| unitPrice | number | - | ✅是 | 单价 |
| subtotal | number | - | 否 | 小计金额 |
| remark | string | - | 否 | 明细备注 |
| partDetail | object | - | 否 | 仅查询返回；创建时不得传入，以 `partId` 引用配件 |

##### 子模型：Part（partDetail字段）
**必填字段**：`name`、`partCode`、`purchasePrice`

| 字段名 | 类型 | 格式 | 是否必填 | 说明 |
|---|---|---|---|---|
| deleted | integer | int32 | 否 | 删除标记 |
| createTime | string | date‑time | 否 | 创建时间 |
| updateTime | string | date‑time | 否 | 更新时间 |
| id | integer | int64 | 否 | 配件主键ID |
| partCode | string | - | ✅是 | 配件编码 |
| name | string | - | ✅是 | 配件名称 |
| model | string | - | 否 | 型号 |
| specification | string | - | 否 | 规格 |
| unit | string | - | 否 | 单位 |
| purchasePrice | number | - | ✅是 | 采购价，最小值≥0 |
| suggestedRetailPrice | number | - | 否 | 建议零售价 |
| stockWarningValue | integer | int32 | 否 | 库存预警值 |
| supplierId | integer | int64 | 否 | 供应商ID |
| category | string | - | 否 | 配件分类 |
| description | string | - | 否 | 配件描述 |

## 响应信息
HTTP状态码：`200`
- description：OK
- Content‑Type：`*/*`
- 返回模型：`ResultPurchaseOrderWithDetails`

### 响应模型 ResultPurchaseOrderWithDetails
| 字段名 | 类型 | 格式 | 说明 |
|---|---|---|---|
| code | integer | int32 | 业务响应码 |
| message | string | - | 返回消息 |
| data | object | - | 返回业务数据，类型：`PurchaseOrderWithDetails` |
| timestamp | integer | int64 | 时间戳 |

## 完整请求示例JSON
```json
{
  "orderNumber": "PO20260807001",
  "totalAmount": 12000.00,
  "status": 1,
  "orderTime": "2026-08-07T10:00:00Z",
  "expectedDeliveryDate": "2026-08-20",
  "createdBy": 1001,
  "remark": "第一批物料采购",
  "orderDetail": [
    {
      "partId": 2001,
      "quantity": 10,
      "unitPrice": 1200.00,
      "subtotal": 12000.00,
      "remark": "配件A采购"
    }
  ]
}
```

## 响应示例JSON
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "deleted": 0,
    "createTime": "2026-08-07T14:00:00Z",
    "updateTime": "2026-08-07T14:00:00Z",
    "id": 10001,
    "orderNumber": "PO20260807001",
    "totalAmount": 12000.00,
    "status": 1,
    "orderTime": "2026-08-07T10:00:00Z",
    "expectedDeliveryDate": "2026-08-20",
    "actualDeliveryDate": null,
    "createdBy": 1001,
    "remark": "第一批物料采购",
    "orderDetail": [
      {
        "deleted": 0,
        "createTime": "2026-08-07T14:00:00Z",
        "updateTime": "2026-08-07T14:00:00Z",
        "id": 20001,
        "orderId": 10001,
        "partId": 2001,
        "quantity": 10,
        "unitPrice": 1200.00,
        "subtotal": 12000.00,
        "remark": "配件A采购",
        "partDetail": {
          "deleted": 0,
          "createTime": "2026-08-01T09:00:00Z",
          "updateTime": "2026-08-01T09:00:00Z",
          "id": 2001,
          "partCode": "P001",
          "name": "轴承",
          "model": "M‑001",
          "specification": "Φ50",
          "unit": "个",
          "purchasePrice": 1200.00,
          "suggestedRetailPrice": 1500.00,
          "stockWarningValue": 5,
          "supplierId": 100,
          "category": "机械配件",
          "description": "工业轴承配件"
        }
      }
    ]
  },
  "timestamp": 1786130400000
}
```

