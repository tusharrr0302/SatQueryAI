EXECUTE_REMOTE_SENSING_ANALYSIS_TOOL = {
    "type": "function",
    "function": {
        "name": "execute_remote_sensing_analysis",
        "description": (
            "Execute a remote sensing analysis using the selected "
            "EO model and dataset."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "model_id": {
                    "type": "string",
                    "description": "ID of the EO model to execute."
                },
                "dataset_ids": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Dataset IDs required for the analysis."
                },
                "analysis_type": {
                    "type": "string",
                    "description": "Analysis operation to perform."
                }
            },
            "required": [
                "model_id",
                "dataset_ids",
                "analysis_type"
            ],
            "additionalProperties": False
        }
    }
}