from langchain_core.tools import tool


@tool
def execute_remote_sensing_analysis(
    model_id: str,
    dataset_ids: list[str],
    analysis_type: str,
) -> dict:
    """
    Execute a remote sensing analysis using an EO model.
    """

    print("    TOOL CALLED")
    print(f"   Model: {model_id}")
    print(f"   Datasets: {dataset_ids}")
    print(f"   Analysis: {analysis_type}")

    return {
        "status": "success",
        "source": "mock",
        "model": model_id,
        "datasets": dataset_ids,
        "analysis_type": analysis_type,
        "message": "Mock remote sensing analysis completed."
    }