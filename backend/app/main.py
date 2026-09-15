from fastapi import FastAPI
from app.graph.workflow import build_graph


app = FastAPI(title="SatQuery AI")

@app.get("/health")
def health():
    return {"status": "ok"}

graph = build_graph()


@app.get("/test-graph")
def test_graph():

    result = graph.invoke({
        "user_query": "Show me how Delhi changed over the last 10 years"
    })

    return result