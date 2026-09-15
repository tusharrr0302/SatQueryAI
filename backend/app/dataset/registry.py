DATASET_REGISTRY = {
    "sentinel-2": {
        "name": "Sentinel-2",
        "provider": "Copernicus",
        "modality": "optical",
        "tasks": [
            "single_image",
            "temporal_change",
            "vegetation",
            "built_up",
        ],
    },
    "sentinel-1": {
        "name": "Sentinel-1",
        "provider": "Copernicus",
        "modality": "sar",
        "tasks": [
            "single_image",
            "temporal_change",
            "built_up",
            "flood",
        ],
    },
}