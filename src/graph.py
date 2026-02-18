from langgraph.graph import StateGraph, START, END

from src.schemas import State
from src.nodes import (
    router_node,
    route_next,
    research_node,
    orchestrator_node,
    fanout,
    worker_node,
    reducer_node
)

def build_graph():
    g = StateGraph(State)

    g.add_node("router", router_node)
    g.add_node("research", research_node)
    g.add_node("orchestrator", orchestrator_node)
    g.add_node("worker", worker_node)
    g.add_node("reducer", reducer_node)

    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router",
        route_next,
        {"research": "research", "orchestrator": "orchestrator"},
    )

    g.add_edge("research", "orchestrator")
    g.add_conditional_edges("orchestrator", fanout, ["worker"])
    g.add_edge("worker", "reducer")
    g.add_edge("reducer", END)

    app = g.compile()
    return app

app = build_graph()
