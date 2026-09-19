from langchain_core.tools import tool
from app.models.manager import model_manager


@tool
def execute_remote_sensing_analysis(
    model_id: str,
    dataset_ids: list[str],
    analysis_type: str,
    query: str = "Show me how Delhi changed over the last 10 years",
) -> dict:
    """
    Execute a remote sensing analysis using an EO model and datasets.
    """
    print("    TOOL CALLED")
    print(f"   Model: {model_id}")
    print(f"   Datasets: {dataset_ids}")
    print(f"   Analysis: {analysis_type}")

    normalized = model_manager.execute(
        model_id=model_id,
        query=query,
        request={
            "aoi": {"name": query.split(" over ")[0].replace("Show me how ", "")},
            "data_requirements": {"datasets": dataset_ids},
            "analysis": {"operation": analysis_type},
            "intent": {"temporal_scope": {}},
        },
    )

    return {
        "status": "success",
        "source": "planetary_computer",
        "model": model_id,
        "datasets": dataset_ids,
        "analysis_type": analysis_type,
        "result": normalized.model_dump(),
        "message": "Remote sensing analysis completed from Planetary Computer imagery."
    }