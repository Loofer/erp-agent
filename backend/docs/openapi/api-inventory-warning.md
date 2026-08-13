# /api/inventory/warning 接口说明文档
## 接口基础信息
|项|内容|
|---|---|
|接口地址|`GET /api/inventory/warning`|
|请求方式|GET|
|标签|库存管理|
|接口摘要|获取库存预警列表|
|operationId|getWarningList|
|响应状态码|200 OK|

> 说明：**该接口无请求参数**，直接GET调用即可，返回低于安全库存的库存预警数据；返回data数组内每条库存记录嵌套零部件完整信息。

## 响应返回整体结构 `ResultListInventoryWithPart`
|字段|类型|说明|
| ---- | ---- | ---- |
|code|integer(int32)|响应业务码|
|message|string|响应提示信息|
|data|Array[InventoryWithPart]|预警库存数据列表，数组元素为库存+零部件信息对象|
|timestamp|integer(int64)|响应时间戳|

### 子对象：InventoryWithPart 库存预警记录
|字段|类型|说明|
| ---- | ---- | ---- |
|id|integer(int64)|库存记录ID|
|partId|integer(int64)|零部件ID|
|currentQuantity|integer(int32)|当前库存数量|
|safetyStock|integer(int32)|安全库存阈值；currentQuantity ≤ safetyStock 触发预警|
|lastInboundTime|string(date‑time)|最近入库时间，ISO日期时间格式|
|lastOutboundTime|string(date‑time)|最近出库时间，ISO日期时间格式|
|warehouseLocation|string|仓库库位|
|deleted|integer(int32)|删除标记，0未删除，1已删除|
|createTime|string(date‑time)|记录创建时间|
|updateTime|string(date‑time)|记录更新时间|
|partDetail|PartInfo|零部件详情对象|

### 子对象：PartInfo 零部件详情（partDetail）
|字段|类型|说明|
| ---- | ---- | ---- |
|id|integer(int64)|零部件ID|
|partCode|string|物料编码|
|name|string|物料名称|
|model|string|型号|
|specification|string|规格|
|unit|string|计量单位|
|purchasePrice|number|采购单价|
|suggestedRetailPrice|number|建议零售价|
|stockWarningValue|integer(int32)|库存预警值|
|supplierId|integer(int64)|所属供应商ID|
|category|string|产品分类|
|description|string|物料描述|
|deleted|integer(int32)|零部件删除标记|
|createTime|string(date‑time)|零部件创建时间|
|updateTime|string(date‑time)|零部件更新时间|

## 返回示例JSON
```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "id": 1,
      "partId": 101,
      "currentQuantity": 5,
      "safetyStock": 20,
      "lastInboundTime": "2026-07-10T10:00:00",
      "lastOutboundTime": "2026-08-01T14:30:00",
      "warehouseLocation": "A‑03‑05",
      "deleted": 0,
      "createTime": "2026-01-05T09:20:00",
      "updateTime": "2026-08-02T11:10:00",
      "partDetail": {
        "id": 101,
        "partCode": "MAT‑00101",
        "name": "轴承",
        "model": "SKF‑6205",
        "specification": "6205深沟球轴承",
        "unit": "个",
        "purchasePrice": 28.5,
        "suggestedRetailPrice": 45,
        "stockWarningValue":15,
        "supplierId": 22,
        "category": "传动配件",
        "description": "设备转动部件轴承",
        "deleted": 0,
        "createTime": "2026‑01‑01T08:00:00",
        "updateTime": "2026‑07‑20T16:22:00"
      }
    }
  ],
  "timestamp": 1754582400000
}
```