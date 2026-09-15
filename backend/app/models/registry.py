MODEL_REGISTRY = {
    "geochat-7b": {
        "name": "GeoChat-7B",
        "tasks": [
            "single_image_vqa",
            "captioning",
            "grounding",
        ],
        "modalities": ["optical"],
    },
    "prithvi-eo-2.0": {
        "name": "Prithvi-EO-2.0",
        "tasks": [
            "temporal_change",
            "vegetation",
            "multispectral",
        ],
        "modalities": ["optical", "multispectral"],
    },
    "terrafm": {
        "name": "TerraFM",
        "tasks": [
            "optical_sar",
            "multisensor",
        ],
        "modalities": ["optical", "sar"],
    },
    "closp": {
        "name": "CLOSP",
        "tasks": [
            "optical_sar",
            "retrieval",
        ],
        "modalities": ["optical", "sar"],
    },
    "vista": {
        "name": "VisTA",
        "tasks": [
            "temporal_change",
        ],
        "modalities": ["optical"],
    },
}