---
name: skill-management
description: Maintain reviewed Deep Agents skills and their registered tool contracts.
---

# Skill Management

Keep each skill focused on a user workflow and list only tools that the runtime
actually registers. When a new business capability is added, define its
Swagger operation in a domain tool module, add it to the explicit tool registry,
cover it with a `MockTransport` test, and then document the workflow here.

Never use a skill document to bypass approval requirements or grant an
unregistered API operation to a subagent.
