import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List

from .paths import DATA_DIR, KNOWLEDGE_BASE_DIR


@dataclass
class ToolResult:
    name: str
    tool_input: str
    data: Any
    summary: str


@dataclass
class ToolDefinition:
    name: str
    description: str
    required_args: List[str]
    handler: Callable[..., ToolResult]


def query_tickets(keyword: str) -> ToolResult:
    tickets = _load_json(DATA_DIR / "tickets.json")
    normalized_keyword = keyword.lower()

    matches = []
    for ticket in tickets:
        searchable = " ".join(
            [
                ticket["id"],
                ticket["customer"],
                ticket["service"],
                ticket["priority"],
                ticket["status"],
                ticket["title"],
                ticket["description"],
                " ".join(ticket["tags"]),
            ]
        ).lower()
        if normalized_keyword in searchable:
            matches.append(ticket)

    return ToolResult(
        name="query_tickets",
        tool_input=keyword,
        data=matches,
        summary="找到 {} 个相关工单".format(len(matches)),
    )


def get_service_metrics(service: str) -> ToolResult:
    metrics_by_service = _load_json(DATA_DIR / "service_metrics.json")
    metrics = metrics_by_service.get(service, {})
    summary = "找到 {} 的指标".format(service) if metrics else "没有找到 {} 的指标".format(service)

    return ToolResult(
        name="get_service_metrics",
        tool_input=service,
        data=metrics,
        summary=summary,
    )


def search_knowledge_base(query: str) -> ToolResult:
    terms = _extract_terms(query)
    matches = []

    for path in sorted(KNOWLEDGE_BASE_DIR.glob("*.md")):
        content = path.read_text(encoding="utf-8")
        score = _score_document(path, content, terms)
        if score > 0:
            matches.append(
                {
                    "source": path.name,
                    "score": score,
                    "excerpt": _make_excerpt(content, terms),
                }
            )

    matches.sort(key=lambda item: item["score"], reverse=True)
    return ToolResult(
        name="search_knowledge_base",
        tool_input=query,
        data=matches,
        summary="找到 {} 篇相关知识库文档".format(len(matches)),
    )


TOOL_REGISTRY: Dict[str, ToolDefinition] = {
    "query_tickets": ToolDefinition(
        name="query_tickets",
        description="按关键词查询企业工单。适合查客户反馈、故障标题、服务名、优先级或标签。",
        required_args=["keyword"],
        handler=query_tickets,
    ),
    "get_service_metrics": ToolDefinition(
        name="get_service_metrics",
        description="查询指定服务的错误率、P95 延迟、Redis 连接数、慢查询等指标。",
        required_args=["service"],
        handler=get_service_metrics,
    ),
    "search_knowledge_base": ToolDefinition(
        name="search_knowledge_base",
        description="按查询词检索运维手册、工单优先级规则和历史处理经验。",
        required_args=["query"],
        handler=search_knowledge_base,
    ),
}


def list_tool_specs() -> List[Dict[str, Any]]:
    return [
        {
            "name": tool.name,
            "description": tool.description,
            "required_args": tool.required_args,
        }
        for tool in TOOL_REGISTRY.values()
    ]


def execute_tool_call(name: str, args: Dict[str, Any]) -> ToolResult:
    tool = TOOL_REGISTRY.get(name)
    tool_input = json.dumps(args, ensure_ascii=False, sort_keys=True)
    if tool is None:
        return ToolResult(
            name=name,
            tool_input=tool_input,
            data=None,
            summary="工具调用被拒绝：{} 不在白名单中".format(name),
        )

    missing_args = [arg for arg in tool.required_args if arg not in args]
    if missing_args:
        return ToolResult(
            name=name,
            tool_input=tool_input,
            data=None,
            summary="工具调用被拒绝：缺少参数 {}".format(", ".join(missing_args)),
        )

    unknown_args = sorted(set(args) - set(tool.required_args))
    if unknown_args:
        return ToolResult(
            name=name,
            tool_input=tool_input,
            data=None,
            summary="工具调用被拒绝：包含未声明参数 {}".format(", ".join(unknown_args)),
        )

    safe_args = {arg: str(args[arg]) for arg in tool.required_args}
    return tool.handler(**safe_args)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_terms(query: str) -> List[str]:
    normalized = query.lower()
    tokens = [token for token in re.split(r"[\s,，。:：?？/\\]+", normalized) if token]
    domain_terms = [
        "支付",
        "失败",
        "redis",
        "超时",
        "连接",
        "工单",
        "优先级",
        "payment",
        "timeout",
        "priority",
    ]
    return sorted(set(tokens + [term for term in domain_terms if term in normalized]))


def _score_document(path: Path, content: str, terms: List[str]) -> int:
    haystack = "{}\n{}".format(path.name, content).lower()
    return sum(1 for term in terms if term and term.lower() in haystack)


def _make_excerpt(content: str, terms: List[str]) -> str:
    compact = " ".join(line.strip() for line in content.splitlines() if line.strip())
    lower_compact = compact.lower()

    positions = [
        lower_compact.find(term.lower())
        for term in terms
        if term and lower_compact.find(term.lower()) >= 0
    ]
    if not positions:
        return compact[:180]

    start = max(min(positions) - 40, 0)
    end = min(start + 220, len(compact))
    return compact[start:end]
