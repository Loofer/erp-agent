---
name: order-management
description: Collect missing procurement-order information through the reviewed human-input workflow.
---

# Order Management

When an order draft has missing required fields, call `request_order_info` with
the draft and the missing field names. The native Deep Agents approval flow
pauses before execution so a reviewer can edit the draft or reject the request.

Do not report that an order was created or updated. No order API operation is
registered in this skeleton yet.
