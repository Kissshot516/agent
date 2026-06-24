import json
from dataclasses import dataclass
from typing import Any, Dict, List

from .llm import LLMError
from .prompts import build_report_messages, build_tool_planning_messages
from .tools import ToolResult, execute_tool_call, list_tool_specs


@dataclass
class AgentStep:
    tool: str
    tool_input: str
    observation: str


@dataclass
class AgentAnswer:
    question: str
    final_answer: str
    steps: List[AgentStep]
    escalation_required: bool


@dataclass
class PlannedToolCall:
    name: str
    args: Dict[str, Any]


@dataclass
class ToolPlan:
    service: str
    tool_calls: List[PlannedToolCall]


class EnterpriseSupportAgent:
    """A learning-first agent with safe tool planning and execution."""

    def __init__(self, chat_model=None):
        self.chat_model = chat_model

    def answer(self, question: str) -> AgentAnswer:
        plan, planning_step = self._plan_tools(question)

        steps = []
        if planning_step is not None:
            steps.append(planning_step)

        tool_results = []
        for tool_call in plan.tool_calls:
            result = execute_tool_call(tool_call.name, tool_call.args)
            tool_results.append(result)
            steps.append(self._to_step(result))

        tickets, metrics, kb_matches = self._collect_evidence(tool_results)

        final_answer, escalation_required = self._synthesize(
            question=question,
            service=plan.service,
            tickets=tickets,
            metrics=metrics,
            kb_matches=kb_matches,
        )
        final_answer = self._maybe_generate_llm_report(
            fallback_answer=final_answer,
            steps=steps,
            question=question,
            service=plan.service,
            tickets=tickets,
            metrics=metrics,
            kb_matches=kb_matches,
            escalation_required=escalation_required,
        )

        return AgentAnswer(
            question=question,
            final_answer=final_answer,
            steps=steps,
            escalation_required=escalation_required,
        )

    def _plan_tools(self, question: str):
        fallback_plan = self._build_rule_based_plan(question)
        if self.chat_model is None:
            return fallback_plan, None

        try:
            messages = build_tool_planning_messages(
                question=question,
                tool_specs=list_tool_specs(),
            )
            raw_plan = self.chat_model.complete(messages)
            plan = self._parse_tool_plan(raw_plan, fallback_service=fallback_plan.service)
            step = AgentStep(
                tool="llm_plan_tools",
                tool_input=self.chat_model.display_name,
                observation="模型生成工具计划：{}".format(
                    ", ".join(tool_call.name for tool_call in plan.tool_calls)
                ),
            )
            return plan, step
        except (LLMError, ValueError, json.JSONDecodeError) as error:
            step = AgentStep(
                tool="llm_plan_tools",
                tool_input=self.chat_model.display_name,
                observation="模型工具规划失败，已回退规则计划：{}".format(error),
            )
            return fallback_plan, step

    def _build_rule_based_plan(self, question: str) -> ToolPlan:
        service = self._infer_service(question)
        topic = self._infer_topic(question, service)
        kb_query = "{} {} 工单优先级".format(question, topic)
        if service == "payment-service":
            kb_query = "{} Redis 超时 连接".format(kb_query)

        return ToolPlan(
            service=service,
            tool_calls=[
                PlannedToolCall(name="query_tickets", args={"keyword": topic}),
                PlannedToolCall(name="get_service_metrics", args={"service": service}),
                PlannedToolCall(name="search_knowledge_base", args={"query": kb_query}),
            ],
        )

    def _parse_tool_plan(self, raw_plan: str, fallback_service: str) -> ToolPlan:
        plan_payload = json.loads(self._extract_json_object(raw_plan))
        if not isinstance(plan_payload, dict):
            raise ValueError("工具计划必须是 JSON object")

        service = str(plan_payload.get("service") or fallback_service)
        raw_tool_calls = plan_payload.get("tool_calls")
        if not isinstance(raw_tool_calls, list) or not raw_tool_calls:
            raise ValueError("工具计划缺少 tool_calls")

        tool_calls = []
        for raw_call in raw_tool_calls:
            if not isinstance(raw_call, dict):
                raise ValueError("tool_calls 中存在非 object 项")

            name = raw_call.get("name")
            args = raw_call.get("args", {})
            if not isinstance(name, str) or not name:
                raise ValueError("工具调用缺少 name")
            if not isinstance(args, dict):
                raise ValueError("{} 的 args 必须是 object".format(name))

            tool_calls.append(PlannedToolCall(name=name, args=args))

        return ToolPlan(service=service, tool_calls=tool_calls)

    def _extract_json_object(self, raw_text: str) -> str:
        stripped = raw_text.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            return stripped

        start = stripped.find("{")
        end = stripped.rfind("}")
        if start < 0 or end < start:
            raise ValueError("模型没有返回 JSON object")
        return stripped[start : end + 1]

    def _collect_evidence(self, tool_results: List[ToolResult]):
        tickets_by_id = {}
        metrics = {}
        kb_matches = []

        for result in tool_results:
            if result.name == "query_tickets" and isinstance(result.data, list):
                for ticket in result.data:
                    tickets_by_id[ticket["id"]] = ticket
            elif result.name == "get_service_metrics" and isinstance(result.data, dict):
                metrics.update(result.data)
            elif result.name == "search_knowledge_base" and isinstance(result.data, list):
                kb_matches.extend(result.data)

        return list(tickets_by_id.values()), metrics, kb_matches

    def _infer_service(self, question: str) -> str:
        lowered = question.lower()
        if "支付" in question or "payment" in lowered:
            return "payment-service"
        if "订单" in question or "order" in lowered:
            return "order-service"
        if "网关" in question or "gateway" in lowered:
            return "gateway"
        return "payment-service"

    def _infer_topic(self, question: str, service: str) -> str:
        if service == "payment-service":
            return "支付"
        if service == "order-service":
            return "订单"
        if service == "gateway":
            return "网关"
        return question

    def _to_step(self, result: ToolResult) -> AgentStep:
        return AgentStep(
            tool=result.name,
            tool_input=result.tool_input,
            observation=result.summary,
        )

    def _maybe_generate_llm_report(
        self,
        fallback_answer,
        steps,
        question,
        service,
        tickets,
        metrics,
        kb_matches,
        escalation_required,
    ):
        if self.chat_model is None:
            return fallback_answer

        try:
            messages = build_report_messages(
                question=question,
                service=service,
                tickets=tickets,
                metrics=metrics,
                kb_matches=kb_matches,
                escalation_required=escalation_required,
            )
            answer = self.chat_model.complete(messages)
            steps.append(
                AgentStep(
                    tool="llm_generate_report",
                    tool_input=self.chat_model.display_name,
                    observation="模型已基于工具证据生成报告",
                )
            )
            return answer
        except LLMError as error:
            steps.append(
                AgentStep(
                    tool="llm_generate_report",
                    tool_input=self.chat_model.display_name,
                    observation="模型调用失败，已回退规则报告：{}".format(error),
                )
            )
            return fallback_answer

    def _synthesize(self, question, service, tickets, metrics, kb_matches):
        if service == "payment-service":
            return self._synthesize_payment_answer(question, tickets, metrics, kb_matches)

        return self._synthesize_generic_answer(question, service, tickets, metrics, kb_matches)

    def _synthesize_payment_answer(self, question, tickets, metrics, kb_matches):
        p1_tickets = [ticket for ticket in tickets if ticket["priority"] == "P1"]
        redis_at_limit = (
            metrics.get("redis_max_clients", 0) > 0
            and metrics.get("redis_connected_clients") == metrics.get("redis_max_clients")
        )
        redis_timeouts = metrics.get("redis_timeout_count", 0)
        escalation_required = bool(p1_tickets and redis_at_limit and redis_timeouts > 0)

        root_cause = "初步判断为 Redis 连接池耗尽，导致 payment-service 调用 Redis 超时，进而拉高支付失败率。"
        evidence = [
            "相关 P1 工单：{}".format(", ".join(ticket["id"] for ticket in p1_tickets) or "暂无"),
            "支付错误率从基线 {} 升至 {}".format(
                metrics.get("baseline_error_rate", "未知"),
                metrics.get("error_rate", "未知"),
            ),
            "P95 延迟从 {}ms 升至 {}ms".format(
                metrics.get("baseline_p95_latency_ms", "未知"),
                metrics.get("p95_latency_ms", "未知"),
            ),
            "Redis 连接数 {}/{}，Redis 超时次数 {}".format(
                metrics.get("redis_connected_clients", "未知"),
                metrics.get("redis_max_clients", "未知"),
                metrics.get("redis_timeout_count", "未知"),
            ),
        ]

        if kb_matches:
            evidence.append("知识库命中：{}，其排查规则支持该判断".format(kb_matches[0]["source"]))

        recommendations = [
            "立即通知支付服务值班工程师，并按 P1 处理。",
            "临时扩容 Redis 连接上限或扩容 Redis 实例，先降低用户支付失败。",
            "排查 payment-service 是否存在连接泄漏、连接池配置过小或慢命令堆积。",
            "增加支付链路的超时、熔断和降级策略，避免 Redis 异常继续放大影响。",
        ]

        final_answer = "\n".join(
            [
                "问题：{}".format(question),
                "",
                "结论：{}".format(root_cause),
                "",
                "证据：",
                *["- {}".format(item) for item in evidence],
                "",
                "建议：",
                *["- {}".format(item) for item in recommendations],
                "",
                "是否需要人工介入：{}".format("是" if escalation_required else "否"),
            ]
        )
        return final_answer, escalation_required

    def _synthesize_generic_answer(self, question, service, tickets, metrics, kb_matches):
        escalation_required = any(ticket["priority"] == "P1" for ticket in tickets)
        final_answer = "\n".join(
            [
                "问题：{}".format(question),
                "",
                "结论：已查询 {} 的相关工单、指标和知识库，但当前第一版 Agent 只内置了支付故障的详细归因模板。".format(service),
                "",
                "证据：",
                "- 相关工单数量：{}".format(len(tickets)),
                "- 指标窗口：{}".format(metrics.get("window", "未找到")),
                "- 知识库命中文档数：{}".format(len(kb_matches)),
                "",
                "下一步：后续课程会把这里改造成由 LangGraph 节点和大模型共同完成的通用分析流程。",
                "",
                "是否需要人工介入：{}".format("是" if escalation_required else "否"),
            ]
        )
        return final_answer, escalation_required
