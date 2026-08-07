# /api/parts/search 接口说明文档
## 基本信息
|项|内容|
|---|---|
|接口路径|`GET /api/parts/search`|
|接口标签|产品/零部件管理|
|接口摘要|搜索零部件|
|operationId|search_1|
|请求方式|GET|

## 请求参数
Query参数（URL查询参数）

|参数名|位置|类型|是否必填|描述|约束|
|---|---|---|---|---|---|
|name|query|string|**true**|零件名称关键字|无|

> 说明：仅支持通过`name`关键字做零部件模糊搜索。

## 返回数据
### 响应状态码：200 OK
返回外层包装对象：**ResultListPart**
|字段|类型|格式|说明|
|---|---|---|---|
|code|integer|int32|响应业务码|
|message|string|-|响应提示信息|
|data|array|-|零部件数据数组，数组元素为`Part`对象|
|timestamp|integer|int64|响应时间戳|

### 子对象：Part 零部件实体
|字段|类型|格式|是否必填|说明|约束|
|---|---|---|---|---|---|
|deleted|integer|int32|否|删除标记|逻辑删除字段|
|createTime|string|date‑time|否|创建时间|时间格式字符串|
|updateTime|string|date‑time|否|更新时间|时间格式字符串|
|id|integer|int64|否|零部件主键ID|-|
|partCode|string|-|**是**|零件编码|必填|
|name|string|-|**是**|零件名称|必填|
|model|string|-|否|型号|-|
|specification|string|-|否|规格|-|
|unit|string|-|否|单位|-|
|purchasePrice|number|-|**是**|采购单价|`minimum:0`，允许等于0|
|suggestedRetailPrice|number|-|否|建议零售价|-|
|stockWarningValue|integer|int32|否|库存预警值|-|
|supplierId|integer|int64|否|关联供应商ID|-|
|category|string|-|否|产品分类|-|
|description|string|-|否|描述信息|-|

## 请求示例
```http
GET /api/parts/search?name=螺丝
```

## 返回示例
```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "deleted": 0,
      "createTime": "2026-01-01T10:00:00",
      "updateTime": "2026-01-02T11:00:00",
      "id": 1001,
      "partCode": "LS‑001",
      "name": "六角螺丝",
      "model": "M8",
      "specification": "8*30mm",
      "unit": "个",
      "purchasePrice": 0.85,
      "suggestedRetailPrice": 1.2,
      "stockWarningValue": 200,
      "supplierId": 5,
      "category": "紧固件",
      "description": "碳钢六角螺丝"
    }
  ],
  "timestamp": 1780000000000
}
```