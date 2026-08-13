# /api/orders/search‑details 接口说明文档
## 基本信息
|项|内容|
|---|---|
|接口路径|`GET /api/orders/search-details`|
|接口标签|采购订单管理|
|接口摘要|搜索订单明细|
|operationId|searchOrderDetails|
|请求方式|GET|

## 请求参数（Query 参数）
|参数名|位置|类型|是否必填|描述|
|---|---|---|---|---|
|partName|query|string|false|零部件名称（模糊匹配）|
|startDate|query|string|false|开始时间，格式支持 `yyyy‑MM‑dd` / `yyyy‑MM‑dd HH:mm:ss`|
|endDate|query|string|false|结束时间，格式支持 `yyyy‑MM‑dd` / `yyyy‑MM‑dd HH:mm:ss`|

> 说明：全部为非必传；不传则不做该条件过滤。

## 返回响应
HTTP 200 OK
返回对象：**ResultListOrderDetailWithPartAndSupplier**

### ResultListOrderDetailWithPartAndSupplier
|字段|类型|格式|说明|
|---|---|---|---|
|code|integer|int32|响应状态码|
|message|string|‑|响应提示信息|
|data|array|‑|订单明细数据数组，数组项为 `OrderDetailWithPartAndSupplier`|
|timestamp|integer|int64|响应时间戳|

### OrderDetailWithPartAndSupplier（data数组元素）
|字段|类型|格式|说明|
|---|---|---|---|
|id|integer|int64|订单明细ID|
|orderId|integer|int64|所属采购订单ID|
|partId|integer|int64|零部件ID|
|quantity|integer|int32|采购数量|
|unitPrice|number|‑|采购单价|
|subtotal|number|‑|明细小计金额|
|remark|string|‑|备注|
|createTime|string|date‑time|创建时间|
|updateTime|string|date‑time|更新时间|
|partDetail|PartWithSupplier|‑|零部件及关联供应商完整信息对象|

### PartWithSupplier
|字段|类型|格式|说明|
|---|---|---|---|
|id|integer|int64|零部件ID|
|partCode|string|‑|零部件编码|
|name|string|‑|零部件名称|
|model|string|‑|型号|
|specification|string|‑|规格|
|unit|string|‑|计量单位|
|purchasePrice|number|‑|采购单价|
|suggestedRetailPrice|number|‑|建议零售价|
|stockWarningValue|integer|int32|库存预警值|
|supplierId|integer|int64|供应商ID|
|category|string|‑|零部件分类|
|description|string|‑|零部件描述|
|createTime|string|date‑time|零部件记录创建时间|
|updateTime|string|date‑time|零部件记录更新时间|
|supplier|SupplierInfo|‑|供应商信息对象|

### SupplierInfo
|字段|类型|格式|说明|
|---|---|---|---|
|id|integer|int64|供应商ID|
|supplierCode|string|‑|供应商编码|
|name|string|‑|供应商名称|
|contactPerson|string|‑|联系人|
|phone|string|‑|联系电话|
|email|string|‑|邮箱|
|address|string|‑|地址|
|creditRating|string|‑|信用评级|
|status|integer|int32|供应商状态|
