---
name: order-management
description: 负责采购订单管理；补全草稿字段后，在创建或更新订单前触发人工审批，审批完成前不得声称订单已写入 ERP。
---

# 采购订单管理

当前支持创建采购订单。草稿必填字段不完整时，调用 `request_order_info`
并传入草稿内容和缺失字段名称，向用户请求补充。

字段完整后调用 `create_order`，并传入完整订单数据及 `orderDetail` 明细。
该调用会触发 Deep Agents 人工审批中断；批准（approve）后才会向 ERP
发送 `POST /api/orders/create`，拒绝（reject）不会执行 ERP 写入操作。

审批完成前不得向用户声称订单已创建或已写入 ERP。

更新订单时，先确认订单 ID 和完整更新数据。字段完整后调用
`update_order(order_id, order)`；批准（approve）后才会发送
`PUT /api/orders/update/{id}`，拒绝（reject）不会执行 ERP 更新操作。
