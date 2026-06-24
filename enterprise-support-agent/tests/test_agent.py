import unittest

from enterprise_support_agent.agent import EnterpriseSupportAgent


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


if __name__ == "__main__":
    unittest.main()
