# Enterprise Support Agent

一个边学边做的企业工单智能分析 Agent 项目。

当前目标：输入一个业务问题，Agent 会查询模拟工单、服务指标和知识库，然后输出根因、证据、处理建议和是否需要人工介入。

当前能力：

- mock 模式下使用规则计划，离线可运行。
- DeepSeek 模式下先让模型生成工具调用计划，再由代码安全执行工具。
- 工具执行经过白名单和参数校验，模型不能直接执行任意动作。
- 模型调用失败时自动回退规则计划或规则报告。

## 为什么做这个项目

这个方向比普通聊天助手更适合作为 Agent 简历项目，因为它覆盖真实岗位常见能力：

- Tool Calling：把查询工单、指标、知识库封装成工具。
- Safe Tool Execution：模型只生成计划，代码负责工具白名单和参数校验。
- RAG：后续把知识库升级成向量检索。
- LangGraph：后续把分析流程改成可控状态图。
- Evaluation：用可控模拟数据验证 Agent 是否找到正确根因。
- Observability：后续展示每一步工具调用和状态变化。

## 模型配置

默认使用 `mock` 模式，不需要 API key。  
如果要使用 DeepSeek，把 `.env.example` 复制为 `.env`，并配置：

```text
LLM_PROVIDER=deepseek
DEEPSEEK_API_KEY=你的 DeepSeek API Key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
```

当前项目没有第三方 Python 依赖，DeepSeek 调用使用标准库 HTTP 请求。

## 运行

mock 模式：

```powershell
cd D:\15832\agent\enterprise-support-agent
$env:PYTHONPATH = "src"
python -m enterprise_support_agent "最近支付失败为什么升高？"
```

DeepSeek 模式：

```powershell
cd D:\15832\agent\enterprise-support-agent
$env:PYTHONPATH = "src"
python -m enterprise_support_agent --provider deepseek "最近支付失败为什么升高？"
```

## 测试

```powershell
cd D:\15832\agent\enterprise-support-agent
$env:PYTHONPATH = "src"
python -m unittest discover -s tests
```

## 当前结构

```text
enterprise-support-agent/
  data/                  # 模拟企业数据
  knowledge_base/        # 模拟知识库
  src/
    enterprise_support_agent/
      agent.py           # Agent 决策与答案生成
      config.py          # 环境变量和模型配置
      llm.py             # DeepSeek 模型调用适配
      prompts.py         # 报告生成提示词
      tools.py           # 工具函数、工具注册表、安全执行器
      main.py            # CLI 入口
  tests/                 # 最小评测/测试
  docs/                  # 学习笔记
```

## 学习路线

1. 不用框架实现最小 Agent 循环。
2. 接入 DeepSeek，让模型基于工具证据生成报告。
3. 让模型生成工具计划，并由代码安全执行。
4. 引入 LangGraph，把流程拆成节点和条件边。
5. 加入知识库向量检索。
6. 加入评测集与执行轨迹。
7. 做一个简单 Web UI 展示 Agent 分析过程。
