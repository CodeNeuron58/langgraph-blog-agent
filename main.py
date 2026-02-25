from src.graph import app

def run(topic: str):
    print(f"Running blog agent for topic: {topic}")
    initial_state = {
        "topic": topic,
        "mode": "",
        "needs_research": False,
        "queries": [],
        "evidence": [],
        "plan": None,
        "sections": [],
        "final": "",
    }
    result = app.invoke(initial_state)
    print("Blog generation complete.")
    return result

def main():
    topic = "Evolution of LLMs till 2026"
    run(topic)

if __name__ == "__main__":
    main()
