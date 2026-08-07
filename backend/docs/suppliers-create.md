# 接口文档：创建供应商
## 接口信息
| 项目 | 内容 |
| ---- | ---- |
| 接口地址 | `/api/suppliers/create` |
| 请求方式 | POST |
| 接口标签 | 供应商管理 |
| 接口简述 | 创建供应商 |
| 操作ID | create |

## 请求参数
请求体 `Body`，`Content‑Type: application/json`，**必传**，引用Schema：`Supplier`

请求体字段说明（Supplier）
| 字段名 | 类型 | 示例值 | 说明 | 是否必填 |
| ---- | ---- | ---- | ---- | ---- |
| supplierCode | string | "string" | 供应商编码 | 用户输入|
| name | string | "string" | 供应商名称 | 用户输入 |
| contactPerson | string | "string" | 联系人 | 用户输入 |
| phone | string | "string" | 联系电话 | 用户输入 |
| email | string | "string" | 邮箱 | 用户输入 |
| address | string | "string" | 地址 | 用户输入 |
| creditRating | string | "string" | 信用等级 | 用户输入 |
| status | integer | 0 | 供应商状态 | 系统默认 |

> 注意：`id、createTime、updateTime、deleted、status` 为后端返回字段，**创建请求不要传入**。

### 请求示例
```json
{
  "supplierCode": "SUP001",
  "name": "XX商贸有限公司",
  "contactPerson": "张三",
  "phone": "13800138000",
  "email": "zhangsan@shturl.",
  "address": "XX省XX市XX区XX街道",
  "creditRating": "A",
  "status": 0
}
```

## 返回结果
HTTP状态码：`200 OK`，返回通用包装对象 `ResultSupplier`

返回字段说明
| 字段 | 类型 | 示例 | 说明 |
|------|------|------|------|
| code | int | 0 | 业务响应码，0代表成功 |
| message | string | "string" | 返回提示信息 |
| timestamp | long | 0 | 时间戳 |
| data | object | {} | 返回供应商实体数据 |
| └ id | int | 0 | 主键ID |
| └ supplierCode | string | "string" | 供应商编码 |
| └ name | string | "string" | 供应商名称 |
| └ contactPerson | string | "string" | 联系人 |
| └ phone | string | "string" | 联系电话 |
| └ email | string | "string" | 邮箱 |
| └ address | string | "string" | 地址 |
| └ creditRating | string | "string" | 信用等级 |
| └ status | int | 0 | 供应商状态 |
| └ deleted | int | 0 | 逻辑删除标记 0未删除 |
| └ createTime | string | "2026-08-07T08:39:32.297Z" | 创建时间 UTC时间 |
| └ updateTime | string | "2026-08-07T08:39:32.297Z" | 更新时间 UTC时间 |

### 返回成功示例
```json
{
  "code": 0,
  "message": "string",
  "data": {
    "deleted": 0,
    "createTime": "2026-08-07T08:39:32.297Z",
    "updateTime": "2026-08-07T08:39:32.297Z",
    "id": 0,
    "supplierCode": "string",
    "name": "string",
    "contactPerson": "string",
    "phone": "string",
    "email": "string",
    "address": "string",
    "creditRating": "string",
    "status": 0
  },
  "timestamp": 0
}
```