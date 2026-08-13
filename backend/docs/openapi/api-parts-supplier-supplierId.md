# 接口文档：获取供应商的产品列表
## 接口基本信息
|项|内容|
|---|---|
|接口路径|`GET /api/parts/supplier/{supplierId}`|
|接口标签|产品/零部件管理|
|接口摘要|获取供应商的产品列表|
|operationId|getBySupplierId|

## 请求参数
### 路径参数
|参数名|位置|类型|是否必填|说明|
|---|---|---|---|---|
|supplierId|path|integer(int64)|✅必填|供应商ID|

> 无 Query 参数、无请求 Body。

## 响应 200 OK
返回通用包装对象 `ResultListPart`

### ResultListPart 结构
|字段|类型|说明|
|---|---|---|
|code|integer(int32)|响应状态码|
|message|string|响应提示信息|
|data|Part[]|零部件数据数组，数组元素为Part对象|
|timestamp|integer(int64)|响应时间戳|

### Part 对象（数组子项）
|字段|类型|约束|说明|
|---|---|---|---|
|deleted|integer(int32)|‑|删除标记|
|createTime|string(date‑time)|‑|创建时间|
|updateTime|string(date‑time)|‑|更新时间|
|id|integer(int64)|‑|零部件ID|
|partCode|string|✅必填|零部件编码|
|name|string|✅必填|零部件名称|
|model|string|‑|型号|
|specification|string|‑|规格|
|unit|string|‑|单位|
|purchasePrice|number|✅必填，≥0|采购单价|
|suggestedRetailPrice|number|‑|建议零售价|
|stockWarningValue|integer(int32)|‑|库存预警值|
|supplierId|integer(int64)|‑|所属供应商ID|
|category|string|‑|产品分类|
|description|string|‑|描述|

## 请求示例
```http
GET /api/parts/supplier/1001 HTTP/1.1
```

## 返回示例
```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "deleted": 0,
      "createTime": "2026-08-07T10:00:00",
      "updateTime": "2026-08-07T10:00:00",
      "id": 1,
      "partCode": "P001",
      "name": "轴承A",
      "model": "M‑01",
      "specification": "φ20mm",
      "unit": "个",
      "purchasePrice": 12.5,
      "suggestedRetailPrice": 20,
      "stockWarningValue": 50,
      "supplierId": 1001,
      "category": "传动件",
      "description": "高速轴承"
    }
  ],
  "timestamp": 1754567890123
}
```
