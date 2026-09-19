MODEL_REGISTRY = {
    "geochat-7b": {
        "name": "GeoChat-7B",
        "provider": "MBZUAI Oryx",
        "architecture": "Grounded Remote Sensing Vision-Language Model (LLaVA-adapted)",
        "tasks": [
            "single_image_vqa",
            "captioning",
            "grounding",
        ],
        "modalities": ["optical"],
        "description": "First grounded vision-language model tailored for high-resolution remote sensing, supporting conversational VQA, detailed scene captioning, and referring expression grounding.",
    },
    "prithvi-eo-2.0": {
        "name": "Prithvi-EO-2.0",
        "provider": "IBM Research / NASA / Jülich",
        "architecture": "Temporal Vision Transformer Foundation Model (300M)",
        "tasks": [
            "temporal_change",
            "vegetation",
            "multispectral",
        ],
        "modalities": ["optical", "multispectral"],
        "description": "Advanced open-source Earth Observation foundation model trained on global HLS multispectral time-series data for change detection, crop dynamics, and ecological forecasting.",
    },
    "terrafm": {
        "name": "TerraFM",
        "provider": "Terra Foundation / OpenEO",
        "architecture": "Multimodal Optical + SAR Sensor Alignment Network",
        "tasks": [
            "optical_sar",
            "multisensor",
            "built_up",
        ],
        "modalities": ["optical", "sar"],
        "description": "Multisensory foundation model fusing optical spectral indices with synthetic aperture radar backscatter for built-up and land cover characterization.",
    },
    "closp": {
        "name": "CLOSP",
        "provider": "CLOSP Research (DarthReca)",
        "architecture": "Contrastive Language Optical SAR Pretraining (ResNet / ViT)",
        "tasks": [
            "optical_sar",
            "retrieval",
            "cross_modal_alignment",
        ],
        "modalities": ["optical", "sar"],
        "description": "Contrastive multimodal bridge aligning natural language descriptions with paired Sentinel-1 SAR and Sentinel-2 optical observations.",
    },
    "vista": {
        "name": "VisTA",
        "provider": "VisTA EO Consortium",
        "architecture": "Spatio-Temporal Attention Network",
        "tasks": [
            "temporal_change",
        ],
        "modalities": ["optical"],
        "description": "Visual Spatio-Temporal Attention network specialized in longitudinal optical change detection and urbanization tracking.",
    },
}