import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from .paths import DATA_DIR, KNOWLEDGE_BASE_DIR


@dataclass
class ToolResult:
    name: str
    tool_input: str
    data: Any
    summary: str


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
