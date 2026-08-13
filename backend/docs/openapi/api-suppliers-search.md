# 接口文档：搜索供应商
## 接口基本信息
|项|内容|
|---|---|
|接口路径|`GET /api/suppliers/search`|
|接口标签|供应商管理|
|接口摘要|搜索供应商|
|operationId|search|
|请求方式|GET|

## 请求参数
Query参数（拼接到url后面）

|参数名|位置|是否必填|类型|描述|
|---|---|---|---|---|
|name|query|**true**|string|供应商名称关键字|

> 请求示例：`GET /api/suppliers/search?name=供应商名`

## 响应 200 OK
整体返回包装对象 `ResultListSupplier`

### ResultListSupplier 响应外层结构
|字段|类型|格式|说明|
|---|---|---|---|
|code|integer|int32|响应业务码|
|message|string|-|响应消息|
|data|array|-|供应商数据数组，数组元素为`Supplier`对象|
|timestamp|integer|int64|响应时间戳|

### Supplier（供应商实体，data数组内元素）
必填字段：`name`、`supplierCode`

|字段|类型|格式|说明|
|---|---|---|---|
|deleted|integer|int32|逻辑删除标记|
|createTime|string|date‑time|创建时间|
|updateTime|string|date‑time|更新时间|
|id|integer|int64|供应商主键ID|
|supplierCode|string|-|供应商编码【必填】|
|name|string|-|供应商名称【必填】|
|contactPerson|string|-|联系人|
|phone|string|-|联系电话|
|email|string|-|邮箱|
|address|string|-|地址|
|creditRating|string|-|信用评级|
|status|integer|int32|供应商状态|

### 返回示例
```json
{
  "code": 200,
  "message": "OK",
  "data": [
    {
      "deleted": 0,
      "createTime": "2026-01-01T10:00:00",
      "updateTime": "2026-01-02T11:00:00",
      "id": 1,
      "supplierCode": "S001",
      "name": "XX供应商",
      "contactPerson": "张三",
      "phone": "13800138000",
      "email": "xxx@shturl.",
      "address": "XX省XX市",
      "creditRating": "A",
      "status": 1
    }
  ],
  "timestamp": 1754000000000
}
```