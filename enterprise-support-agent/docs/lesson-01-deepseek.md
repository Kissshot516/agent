# 第 1 课：接入 DeepSeek

这一课把“最终报告生成”交给真实 LLM，但仍然保留工具查询的确定性。

当前流程：

1. 用户输入问题。
2. Agent 根据规则判断服务和主题。
3. 工具查询工单、指标、知识库。
4. 规则先生成一份兜底报告。
5. 如果启用 DeepSeek，把工具证据交给模型生成更自然的报告。
6. 如果模型失败，回退到规则报告。

为什么这样设计：

- 模型负责语言组织和分析表达。
- 工具负责事实查询。
- 规则兜底保证模型服务不可用时仍能返回结果。
- 测试默认不依赖真实 API，保证项目可复现。

关键文件：

- `config.py`：读取 `.env` 和环境变量。
- `llm.py`：封装 DeepSeek Chat API 调用。
- `prompts.py`：定义模型生成报告时的系统提示词。
- `agent.py`：先查工具，再选择是否调用模型。

运行 DeepSeek：

```powershell
cd D:\15832\agent\enterprise-support-agent
$env:PYTHONPATH = "src"
python -m enterprise_support_agent --provider deepseek "最近支付失败为什么升高？"
```

如果没有配置 `DEEPSEEK_API_KEY`，命令会提示配置错误。
