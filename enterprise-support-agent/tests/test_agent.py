import unittest

from enterprise_support_agent.agent import EnterpriseSupportAgent
from enterprise_support_agent.llm import LLMError


class SuccessfulChatModel:
    display_name = "test:success"

    def complete(self, messages):
        return "LLM 生成的报告：Redis 连接池耗尽，需要人工介入。"


class FailingChatModel:
    display_name = "test:failure"

    def complete(self, messages):
        raise LLMError("simulated failure")


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
        agent = EnterpriseSupportAgent(chat_model=SuccessfulChatModel())

        result = agent.answer("最近支付失败为什么升高？")

        self.assertIn("LLM 生成的报告", result.final_answer)
        self.assertEqual(result.steps[-1].tool, "llm_generate_report")

    def test_agent_falls_back_when_llm_fails(self):
        agent = EnterpriseSupportAgent(chat_model=FailingChatModel())

        result = agent.answer("最近支付失败为什么升高？")

        self.assertIn("Redis 连接池耗尽", result.final_answer)
        self.assertEqual(result.steps[-1].tool, "llm_generate_report")
        self.assertIn("回退规则报告", result.steps[-1].observation)


if __name__ == "__main__":
    unittest.main()
