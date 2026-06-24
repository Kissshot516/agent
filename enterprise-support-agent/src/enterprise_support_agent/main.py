import argparse
from typing import List, Optional

from .agent import EnterpriseSupportAgent


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Enterprise Support Agent CLI")
    parser.add_argument(
        "question",
        nargs="*",
        help="需要 Agent 分析的问题，例如：最近支付失败为什么升高？",
    )
    args = parser.parse_args(argv)

    question = " ".join(args.question).strip() or "最近支付失败为什么升高？"
    agent = EnterpriseSupportAgent()
    answer = agent.answer(question)

    print("执行轨迹")
    print("=" * 40)
    for index, step in enumerate(answer.steps, start=1):
        print("{}. {}({}) -> {}".format(index, step.tool, step.tool_input, step.observation))

    print()
    print("最终回答")
    print("=" * 40)
    print(answer.final_answer)
