import argparse
from typing import List, Optional

from .agent import EnterpriseSupportAgent
from .config import resolve_llm_settings
from .llm import LLMError, create_chat_model


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(description="Enterprise Support Agent CLI")
    parser.add_argument(
        "--provider",
        choices=["mock", "deepseek"],
        default=None,
        help="LLM provider. Defaults to deepseek when DEEPSEEK_API_KEY exists, otherwise mock.",
    )
    parser.add_argument(
        "question",
        nargs="*",
        help="需要 Agent 分析的问题，例如：最近支付失败为什么升高？",
    )
    args = parser.parse_args(argv)

    question = " ".join(args.question).strip() or "最近支付失败为什么升高？"
    try:
        llm_settings = resolve_llm_settings(args.provider)
        chat_model = create_chat_model(llm_settings)
    except (ValueError, LLMError) as error:
        raise SystemExit("LLM 配置错误：{}".format(error))

    agent = EnterpriseSupportAgent(chat_model=chat_model)
    answer = agent.answer(question)

    model_label = chat_model.display_name if chat_model else "mock:local-rules"
    print("模型模式：{}".format(model_label))
    print()
    print("执行轨迹")
    print("=" * 40)
    for index, step in enumerate(answer.steps, start=1):
        print("{}. {}({}) -> {}".format(index, step.tool, step.tool_input, step.observation))

    print()
    print("最终回答")
    print("=" * 40)
    print(answer.final_answer)
