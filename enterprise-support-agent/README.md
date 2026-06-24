# Enterprise Support Agent

一个边学边做的企业工单智能分析 Agent 项目。

当前第 1 版目标：输入一个业务问题，Agent 会查询模拟工单、服务指标和知识库，然后输出根因、证据、处理建议和是否需要人工介入。

## 为什么做这个项目

这个方向比普通聊天助手更适合作为 Agent 简历项目，因为它覆盖真实岗位常见能力：

- Tool Calling：把查询工单、指标、知识库封装成工具。
- RAG：后续把知识库升级成向量检索。
- LangGraph：后续把分析流程改成可控状态图。
- Evaluation：用可控模拟数据验证 Agent 是否找到正确根因。
- Observability：后续展示每一步工具调用和状态变化。

## 运行

当前版本没有外部依赖。

```powershell
cd D:\15832\agent\enterprise-support-agent
$env:PYTHONPATH = "src"
python -m enterprise_support_agent "最近支付失败为什么升高？"
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
      tools.py           # 工具函数
      main.py            # CLI 入口
  tests/                 # 最小评测/测试
  docs/lesson-00.md      # 学习笔记
```

## 学习路线

1. 不用框架实现最小 Agent 循环。
2. 接入真实 LLM，让模型参与分类和工具选择。
3. 引入 LangGraph，把流程拆成节点和条件边。
4. 加入知识库向量检索。
5. 加入评测集与执行轨迹。
6. 做一个简单 Web UI 展示 Agent 分析过程。
