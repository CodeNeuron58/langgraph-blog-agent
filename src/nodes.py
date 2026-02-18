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


def _tavily_search(query: str, max_results: int = 5) -> List[dict]:
    tool = TavilySearch(max_results=max_results)
    try:
        response = tool.invoke({"query": query})
        # If it returns a dict with 'results', return that list
        if isinstance(response, dict) and "results" in response:
            return response["results"]
        # If it returns a list directly (some versions/configs), return it
        if isinstance(response, list):
            return response
        return []
    except Exception as e:
        print(f"Error in Tavily search: {e}")
        return []


def research_node(state: State) -> dict:

    raw_results = []
    for q in state.get("queries", [])[:8]:
        raw_results.extend(_tavily_search(q, max_results=6))

    if not raw_results:
        return {"evidence": []}

    extractor = llm.with_structured_output(EvidencePack)

    pack = extractor.invoke(
        [
            SystemMessage(content=RESEARCH_SYSTEM),
            HumanMessage(content=f"Raw results:\n{raw_results}"),
        ]
    )

    dedup = {}
    for e in pack.evidence:
        if e.url:
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
    final_md = f"# {plan.blog_title}\n\n{body}\n"

    filename = f"generated_blogs/{plan.blog_title.replace(' ', '_')}.md"
    Path(filename).write_text(final_md, encoding="utf-8")

    return {"final": final_md}
