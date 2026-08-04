---
name: order-management
description: 负责采购订单管理；当前支持创建采购订单——补全草稿字段后触发人工审批中断，等待批准、编辑或拒绝，审批完成前不得声称订单已写入 ERP。
---

# 采购订单管理

当前支持创建采购订单。草稿必填字段不完整时，调用 `request_order_info`
并传入草稿内容和缺失字段名称，向用户请求补充。

字段完整后调用 `request_order_info` 提交草稿，触发 Deep Agents 人工审批中断；
审批结果分三种：批准（approve）、编辑（edit）、拒绝（reject），
处理方式参见子代理配置。

审批完成前不得向用户声称订单已创建或已写入 ERP。
