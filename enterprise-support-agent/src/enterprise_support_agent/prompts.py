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
