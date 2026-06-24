import json
from typing import Any, Dict, List


REPORT_SYSTEM_PROMPT = """
你是一个企业工单智能分析 Agent，负责基于工具返回的证据生成排查报告。

规则：
1. 只能使用用户问题和工具证据，不要编造不存在的工单、指标、日志或知识库。
2. 如果证据不足，要明确说明“不足以判断”，并写出还需要查询什么。
3. 输出必须包含：结论、关键证据、处理建议、是否需要人工介入。
4. 语气专业、简洁，面向一线支持工程师。
""".strip()


TOOL_PLANNING_SYSTEM_PROMPT = """
你是企业工单分析 Agent 的工具调用规划器。

你的任务：
1. 阅读用户问题。
2. 从可用工具中选择需要调用的工具。
3. 只输出 JSON，不要输出 Markdown、解释或多余文字。

约束：
1. 只能使用可用工具列表中的工具名。
2. 只能使用工具声明的参数名。
3. 不要编造工具，也不要请求读取本地文件、执行命令或访问外部网络。
4. 如果问题涉及支付、订单、网关等服务，优先查询工单、服务指标和知识库。

输出格式：
{
  "service": "payment-service",
  "tool_calls": [
    {"name": "query_tickets", "args": {"keyword": "支付"}},
    {"name": "get_service_metrics", "args": {"service": "payment-service"}},
    {"name": "search_knowledge_base", "args": {"query": "支付失败 Redis 超时 工单优先级"}}
  ]
}
""".strip()


def build_tool_planning_messages(
    question: str,
    tool_specs: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    user_prompt = "\n".join(
        [
            "用户问题：{}".format(question),
            "",
            "可用工具：",
            json.dumps(tool_specs, ensure_ascii=False, indent=2),
        ]
    )
    return [
        {"role": "system", "content": TOOL_PLANNING_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]


def build_report_messages(
    question: str,
    service: str,
    tickets: List[Dict[str, Any]],
    metrics: Dict[str, Any],
    kb_matches: List[Dict[str, Any]],
    escalation_required: bool,
) -> List[Dict[str, str]]:
    evidence = {
        "question": question,
        "service": service,
        "tickets": tickets,
        "metrics": metrics,
        "knowledge_base_matches": kb_matches,
        "rule_based_escalation_required": escalation_required,
    }
    user_prompt = "\n".join(
        [
            "请根据以下证据生成工单分析报告。",
            "",
            json.dumps(evidence, ensure_ascii=False, indent=2),
        ]
    )
    return [
        {"role": "system", "content": REPORT_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
