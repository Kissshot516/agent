import unittest

from enterprise_support_agent.agent import EnterpriseSupportAgent
from enterprise_support_agent.llm import LLMError


class PlanningAndReportChatModel:
    display_name = "test:success"

    def complete(self, messages):
        system_prompt = messages[0]["content"]
        if "工具调用规划器" in system_prompt:
            return """
            {
              "service": "payment-service",
              "tool_calls": [
                {"name": "query_tickets", "args": {"keyword": "支付"}},
                {"name": "get_service_metrics", "args": {"service": "payment-service"}},
                {"name": "search_knowledge_base", "args": {"query": "支付失败 Redis 超时 工单优先级"}}
              ]
            }
            """
        return "LLM 生成的报告：Redis 连接池耗尽，需要人工介入。"


class FailingChatModel:
    display_name = "test:failure"

    def complete(self, messages):
        raise LLMError("simulated failure")


class UnsafeToolPlanChatModel:
    display_name = "test:unsafe"

    def complete(self, messages):
        system_prompt = messages[0]["content"]
        if "工具调用规划器" in system_prompt:
            return """
            {
              "service": "payment-service",
              "tool_calls": [
                {"name": "read_local_file", "args": {"path": "C:/secret.txt"}},
                {"name": "query_tickets", "args": {"keyword": "支付"}}
              ]
            }
            """
        return "LLM 生成的报告：证据不足，需要人工复核。"


class EnterpriseSupportAgentTest(unittest.TestCase):
    def test_payment_question_finds_redis_root_cause(self):
        agent = EnterpriseSupportAgent()

        result = agent.answer("最近支付失败为什么升高？")

        self.assertTrue(result.escalation_required)
        self.assertIn("Redis 连接池耗尽", result.final_answer)
        self.assertIn("TCK-1001", result.final_answer)
        self.assertIn("TCK-1002", result.final_answer)
        self.assertIn("payment_failure_runbook.md", result.final_answer)

    def test_agent_records_tool_steps(self):
        agent = EnterpriseSupportAgent()

        result = agent.answer("最近支付失败为什么升高？")

        self.assertEqual(
            [step.tool for step in result.steps],
            ["query_tickets", "get_service_metrics", "search_knowledge_base"],
        )

    def test_agent_can_use_llm_report(self):
        agent = EnterpriseSupportAgent(chat_model=PlanningAndReportChatModel())

        result = agent.answer("最近支付失败为什么升高？")

        self.assertIn("LLM 生成的报告", result.final_answer)
        self.assertEqual(result.steps[0].tool, "llm_plan_tools")
        self.assertEqual(result.steps[-1].tool, "llm_generate_report")

    def test_agent_executes_llm_tool_plan(self):
        agent = EnterpriseSupportAgent(chat_model=PlanningAndReportChatModel())

        result = agent.answer("最近支付失败为什么升高？")

        self.assertEqual(
            [step.tool for step in result.steps[:4]],
            ["llm_plan_tools", "query_tickets", "get_service_metrics", "search_knowledge_base"],
        )
        self.assertTrue(result.escalation_required)

    def test_agent_falls_back_when_llm_fails(self):
        agent = EnterpriseSupportAgent(chat_model=FailingChatModel())

        result = agent.answer("最近支付失败为什么升高？")

        self.assertIn("Redis 连接池耗尽", result.final_answer)
        self.assertEqual(result.steps[-1].tool, "llm_generate_report")
        self.assertIn("回退规则报告", result.steps[-1].observation)

    def test_agent_rejects_unregistered_tool_from_llm_plan(self):
        agent = EnterpriseSupportAgent(chat_model=UnsafeToolPlanChatModel())

        result = agent.answer("最近支付失败为什么升高？")

        rejected_step = next(step for step in result.steps if step.tool == "read_local_file")
        self.assertIn("不在白名单", rejected_step.observation)


if __name__ == "__main__":
    unittest.main()
