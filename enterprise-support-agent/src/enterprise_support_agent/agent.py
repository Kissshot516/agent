from dataclasses import dataclass
from typing import List

from .llm import LLMError
from .prompts import build_report_messages
from .tools import ToolResult, get_service_metrics, query_tickets, search_knowledge_base


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


class EnterpriseSupportAgent:
    """A tiny deterministic agent used to learn the agent loop before adding LLMs."""

    def __init__(self, chat_model=None):
        self.chat_model = chat_model

    def answer(self, question: str) -> AgentAnswer:
        service = self._infer_service(question)
        topic = self._infer_topic(question, service)

        ticket_result = query_tickets(topic)
        metric_result = get_service_metrics(service)
        kb_query = self._build_knowledge_query(question, topic, metric_result.data)
        kb_result = search_knowledge_base(kb_query)

        steps = [
            self._to_step(ticket_result),
            self._to_step(metric_result),
            self._to_step(kb_result),
        ]

        final_answer, escalation_required = self._synthesize(
            question=question,
            service=service,
            tickets=ticket_result.data,
            metrics=metric_result.data,
            kb_matches=kb_result.data,
        )
        final_answer = self._maybe_generate_llm_report(
            fallback_answer=final_answer,
            steps=steps,
            question=question,
            service=service,
            tickets=ticket_result.data,
            metrics=metric_result.data,
            kb_matches=kb_result.data,
            escalation_required=escalation_required,
        )

        return AgentAnswer(
            question=question,
            final_answer=final_answer,
            steps=steps,
            escalation_required=escalation_required,
        )

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

    def _build_knowledge_query(self, question, topic, metrics):
        query_parts = [question, topic, "工单优先级"]
        if metrics.get("redis_timeout_count", 0) > 0:
            query_parts.extend(["Redis", "超时", "连接"])
        return " ".join(query_parts)

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
