"""
app/orchestrator/sar_optical_selector.py
─────────────────────────────────────────────────────────────────────────────
LLM-driven SAR+optical model selector.

PURPOSE:
  This module provides an LLM-based selector that chooses between CLOSP and
  TerraFM (or both) for SAR+optical analysis tasks based on query semantics.

  The selector is NOT used as a separate routing step in the main graph —
  instead, the orchestrator LLM embeds the selection directly in the
  `selected_models` field of the analyze_sar_optical tool call arguments.
  This module provides:
    1. A standalone helper for use in testing or alternative pipelines.
    2. Documentation of the selection logic for human reviewers.

CRITICAL RULE:
  Model selection MUST be semantics-driven, not keyword-driven.
  Do NOT implement: "if 'flood' in query: return 'closp'"
  The LLM reads the full query and decides based on meaning.

MODEL PROFILES:
  CLOSP (DarthReca/closp):
    - Contrastive cross-modal embedding model
    - SAR ↔ optical similarity and alignment
    - Flood mapping (SAR penetrates cloud)
    - Building damage assessment (double-bounce anomalies)
    - Cross-modal retrieval and structural change detection

  TerraFM (mbzuai-oryx/TerraFM):
    - Large multisensor foundation model
    - Terrain / land-cover classification
    - Scene-level understanding (SAR + optical fusion)
    - Multi-spectral + SAR data for holistic scene analysis
"""

from __future__ import annotations

from typing import Literal
from loguru import logger

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from app.config import settings


# ── Pydantic output schema for the LLM-driven selector ───────────────────────

class SAROpticalModelSelection(BaseModel):
    """Structured output from the SAR+optical model selector LLM call."""

    selected_models: Literal["closp", "terrafm", "both"] = Field(
        description=(
            "Which specialist model(s) to invoke for this SAR+optical analysis. "
            "Choose 'closp' for cross-modal similarity, flood mapping, or damage "
            "assessment. Choose 'terrafm' for terrain/land-cover classification or "
            "broad scene understanding. Choose 'both' for comprehensive analysis "
            "that requires insights from both specialists."
        )
    )
    rationale: str = Field(
        description=(
            "Brief explanation (≤2 sentences) of why this selection is semantically "
            "appropriate for the query. Do NOT explain keyword matching — explain the "
            "task nature and which model's capabilities fit best."
        )
    )


# ── System prompt for the selector ───────────────────────────────────────────

SELECTOR_SYSTEM_PROMPT = """\
You are a specialist geospatial AI routing system.
Your task is to select the most appropriate SAR+optical fusion model for a given query.

You have two specialist models available:

1. CLOSP (Cross-modal Learning for SAR and Optical image Pairs)
   - Contrastive embedding model that aligns SAR and optical in shared feature space
   - Best for: flood mapping, building damage assessment, cross-modal similarity,
     structural change detection via embedding distance, cloud-penetration analysis

2. TerraFM (Terrain Foundation Model)
   - Large multisensor geospatial foundation model
   - Best for: terrain classification, land-cover mapping, scene-level understanding,
     multi-spectral + SAR data fusion for holistic analysis

Select 'both' when the query would genuinely benefit from both specialists.

Important: Base your selection on the SEMANTICS and INTENT of the query, not on
the presence of specific keywords. Think about what kind of task this is and which
model's capabilities are a better fit.

You must return a structured JSON response with:
  - selected_models: "closp" | "terrafm" | "both"
  - rationale: brief semantic justification (≤2 sentences)
"""

SELECTOR_USER_TEMPLATE = """\
Query: {query}

SAR image available: {has_sar}
Optical image available: {has_optical}

Select the most appropriate model(s) for this analysis.
"""


# ── The selector class ────────────────────────────────────────────────────────

class SAROpticalSelector:
    """
    LLM-driven selector for SAR+optical specialist models.

    Uses a structured output call to choose between CLOSP, TerraFM, or both,
    based on semantic understanding of the query and available image modalities.

    This class is used:
      - In testing, to verify that the selector makes sensible choices
      - As a standalone utility for alternative pipelines
      - In the main graph, the selection is embedded in the LLM tool call args
        (the orchestrator LLM populates `selected_models` directly)
    """

    def __init__(self) -> None:
        self._llm = ChatOpenAI(
            model=settings.llm_model,
            openai_api_key=settings.llm_api_key,
            openai_api_base=settings.llm_base_url,
            max_tokens=256,
            temperature=0,
        ).with_structured_output(SAROpticalModelSelection)

        self._prompt = ChatPromptTemplate.from_messages([
            ("system", SELECTOR_SYSTEM_PROMPT),
            ("human", SELECTOR_USER_TEMPLATE),
        ])

        self._chain = self._prompt | self._llm

    def select(
        self,
        query: str,
        sar_image: str | None = None,
        optical_image: str | None = None,
    ) -> SAROpticalModelSelection:
        """
        Select the most appropriate SAR+optical model(s) for the given query.

        Args:
            query:         The user's analysis question / intent
            sar_image:     Whether a SAR image is available (for context)
            optical_image: Whether an optical image is available (for context)

        Returns:
            SAROpticalModelSelection with selected_models and rationale
        """
        if settings.model_mode != "real":
            # In mock mode, return a deterministic mock selection
            logger.debug("[SAROpticalSelector] Mock mode — returning mock selection")
            return SAROpticalModelSelection(
                selected_models="closp",
                rationale=(
                    "Mock mode: defaulting to CLOSP for demonstration. "
                    "In real mode, the LLM makes a semantic selection."
                ),
            )

        logger.debug(f"[SAROpticalSelector] Selecting model for query: {query!r}")

        result = self._chain.invoke({
            "query": query,
            "has_sar": "yes" if sar_image else "no",
            "has_optical": "yes" if optical_image else "no",
        })

        logger.info(
            f"[SAROpticalSelector] Selected: {result.selected_models!r} | "
            f"Rationale: {result.rationale}"
        )

        return result
