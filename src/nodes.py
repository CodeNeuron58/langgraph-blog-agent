from pathlib import Path
from typing import List, Dict, Any
from dotenv import load_dotenv

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_tavily import TavilySearch
from langgraph.types import Send

from src.schemas import (
    State,
    RouterDecision,
    EvidencePack,
    Plan,
    Task,
    EvidenceItem
)
from src.prompts import (
    ROUTER_SYSTEM,
    RESEARCH_SYSTEM,
    ORCH_SYSTEM,
    WORKER_SYSTEM
)

load_dotenv()

llm = ChatGroq(model="llama-3.3-70b-versatile")

def router_node(state: State) -> dict:
    decider = llm.with_structured_output(RouterDecision)

    decision = decider.invoke(
        [
            SystemMessage(content=ROUTER_SYSTEM),
            HumanMessage(content=f"Topic: {state['topic']}"),
        ]
    )

    return {
        "needs_research": decision.needs_research,
        "mode": decision.mode,
        "queries": decision.queries,
    }


def route_next(state: State) -> str:
    return "research" if state["needs_research"] else "orchestrator"


def _tavily_search(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    tool = TavilySearch(max_results=max_results)
    # Fix 1: Pass query string directly, not a dict
    result = tool.invoke(query)
    # Fix 2: Tavily returns a dict with 'results' key, not a list directly
    # Also handle the case where result might be None or empty
    if not result:
        return []
    # Fix 3: Extract the actual results list from the response object
    # TavilySearch returns an object with .results or dict with 'results'
    if hasattr(result, 'results'):
        return result.results
    elif isinstance(result, dict):
        return result.get('results', [])
    return []


def research_node(state: State) -> dict:
    raw_results = []
    # Limit to 8 queries as intended
    for q in state.get("queries", [])[:8]:
        results = _tavily_search(q, max_results=6)
        raw_results.extend(results)

    if not raw_results:
        return {"evidence": []}

    # Fix 4: Ensure raw_results is properly serialized for the LLM
    import json
    results_text = json.dumps(raw_results, indent=2, default=str)

    extractor = llm.with_structured_output(EvidencePack)

    pack = extractor.invoke(
        [
            SystemMessage(content=RESEARCH_SYSTEM),
            HumanMessage(content=f"Raw results:\n{results_text}"),
        ]
    )

    # Deduplication logic (unchanged, looks correct)
    dedup = {}
    for e in pack.evidence:
        if e.url and e.url.startswith(('http://', 'https://')):  # Fix 5: Validate URL format
            dedup[e.url] = e

    return {"evidence": list(dedup.values())}


def orchestrator_node(state: State) -> dict:
    planner = llm.with_structured_output(Plan)

    plan = planner.invoke(
        [
            SystemMessage(content=ORCH_SYSTEM),
            HumanMessage(
                content=(
                    f"Topic: {state['topic']}\n"
                    f"Mode: {state['mode']}\n"
                    f"Evidence:\n{[e.model_dump() for e in state.get('evidence', [])][:20]}"
                )
            ),
        ]
    )

    return {"plan": plan}


def fanout(state: State):
    return [
        Send(
            "worker",
            {
                "task": task.model_dump(),
                "topic": state["topic"],
                "mode": state["mode"],
                "plan": state["plan"].model_dump(),
                "evidence": [e.model_dump() for e in state.get("evidence", [])],
            },
        )
        for task in state["plan"].tasks
    ]


def worker_node(payload: dict) -> dict:

    task = Task(**payload["task"])
    plan = Plan(**payload["plan"])

    bullets_text = "\n- " + "\n- ".join(task.bullets)

    section_md = llm.invoke(
        [
            SystemMessage(content=WORKER_SYSTEM),
            HumanMessage(
                content=(
                    f"Blog title: {plan.blog_title}\n"
                    f"Audience: {plan.audience}\n"
                    f"Tone: {plan.tone}\n"
                    f"Blog kind: {plan.blog_kind}\n"
                    f"Topic: {payload['topic']}\n"
                    f"Mode: {payload['mode']}\n\n"
                    f"Section title: {task.title}\n"
                    f"Goal: {task.goal}\n"
                    f"Target words: {task.target_words}\n"
                    f"requires_code: {task.requires_code}\n"
                    f"Bullets:{bullets_text}\n"
                )
            ),
        ]
    ).content.strip()

    return {"sections": [(task.id, section_md)]}


def reducer_node(state: State) -> dict:
    plan = state["plan"]

    ordered_sections = [
        md for _, md in sorted(state["sections"], key=lambda x: x[0])
    ]

    body = "\n\n".join(ordered_sections).strip()
    
    unique_tags = sorted(list(set([tag for task in plan.tasks for tag in task.tags])))
    tags_str = ", ".join(unique_tags) if unique_tags else "None"
    
    final_md = (
        f"# {plan.blog_title}\n\n"
        f"*Target Audience: {plan.audience} | Scope: {plan.blog_kind.replace('_', ' ').title()}*\n\n"
        f"---\n\n"
        f"{body}\n\n"
        f"---\n\n"
        f"**Tags:** {tags_str}\n"
    )

    filename = f"generated_blogs/{plan.blog_title.replace(' ', '_')}.md"
    Path(filename).write_text(final_md, encoding="utf-8")

    return {"final": final_md}
