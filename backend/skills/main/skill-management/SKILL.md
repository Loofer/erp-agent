---
名称：技能管理
描述：维护已审核的深度智能体技能及其已注册的工具契约。
---

# 技能管理
每项技能需聚焦单一用户业务流程，仅罗列运行时实际完成注册的工具。新增业务能力时，需在领域工具模块中定义对应的 Swagger 接口操作，将接口加入显式工具注册表，配套编写基于`MockTransport`的模拟传输测试，随后在此处完成业务流程文档编写。

严禁借助技能文档规避审批流程，或是向子智能体授予未注册的API操作权限。

### 术语注释（便于技术理解）
1. Deep Agents：深度智能体（AI智能代理程序）
2. tool contracts：工具契约（工具调用接口规范）
3. runtime：运行时
4. Swagger operation：Swagger接口定义
5. domain tool module：领域工具模块
6. explicit tool registry：显式工具注册表
7. MockTransport：模拟传输层（单元测试组件）
8. subagent：子智能体