# 第 2 课：模型规划工具，代码安全执行

这一课把 Agent 从“固定工具调用”升级成“模型生成工具计划”。

旧流程：

1. 代码固定调用 `query_tickets`。
2. 代码固定调用 `get_service_metrics`。
3. 代码固定调用 `search_knowledge_base`。
4. 模型只负责生成最终报告。

新流程：

1. 用户输入问题。
2. 模型输出 JSON 工具计划。
3. 代码解析 JSON。
4. 代码检查工具是否在白名单里。
5. 代码检查参数是否符合声明。
6. 代码执行工具并收集证据。
7. 模型基于证据生成报告。

核心概念：

- 模型负责“决策建议”，比如想查哪个工具。
- 代码负责“权限控制”，比如这个工具能不能执行。
- 工具负责“事实查询”，比如工单、指标、知识库。
- 测试负责“质量兜底”，比如越权工具必须被拒绝。

为什么不能让模型直接执行工具：

- 模型可能幻觉出不存在的工具。
- 模型可能给错参数名。
- 模型可能请求危险动作，比如读本地文件、执行命令、访问外部服务。
- 企业 Agent 必须有审计边界，知道每一步是谁决定的、谁执行的。

本课新增或改动：

- `tools.py`
  - 新增 `TOOL_REGISTRY`：工具白名单。
  - 新增 `list_tool_specs()`：把工具说明交给模型。
  - 新增 `execute_tool_call()`：统一校验并执行工具。

- `prompts.py`
  - 新增 `TOOL_PLANNING_SYSTEM_PROMPT`：要求模型只输出 JSON 工具计划。
  - 新增 `build_tool_planning_messages()`：构造工具规划消息。

- `agent.py`
  - 新增 `ToolPlan` 和 `PlannedToolCall`。
  - 新增 `_plan_tools()`：先让模型规划，失败则回退规则计划。
  - 新增 `_parse_tool_plan()`：解析模型 JSON。
  - 新增 `_collect_evidence()`：从工具结果里整理工单、指标、知识库。

- `tests/test_agent.py`
  - 测试模型正常规划。
  - 测试模型失败时回退。
  - 测试未注册工具会被拒绝。

工具计划示例：

```json
{
  "service": "payment-service",
  "tool_calls": [
    {"name": "query_tickets", "args": {"keyword": "支付"}},
    {"name": "get_service_metrics", "args": {"service": "payment-service"}},
    {"name": "search_knowledge_base", "args": {"query": "支付失败 Redis 超时 工单优先级"}}
  ]
}
```

这一课之后，Agent 已经具备了一个真实工程项目该有的雏形：模型能参与决策，但不能越过代码的安全边界。
