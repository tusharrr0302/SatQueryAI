"""
tests/test_orchestrator.py
─────────────────────────────────────────────────────────────────────────────
Integration tests for the orchestrator agent and FastAPI endpoint.

NOTE: These tests have been updated for the LangGraph migration.
  - The agent now uses ChatOpenAI + LangGraph StateGraph internally.
  - We mock `agent._graph.invoke()` to bypass real LLM calls.
  - The public OrchestratorAgent.run() interface is unchanged.

Tests verify:
  - The orchestrator correctly processes text responses from the LLM
  - The orchestrator correctly processes tool_call responses from the LLM
  - Tool call records are correctly extracted from the message history
  - The FastAPI endpoint returns the correct response structure

Run with:
  cd ai-service
  pytest tests/test_orchestrator.py -v
"""

import json
import pytest
from unittest.mock import MagicMock, patch, create_autospec
from fastapi.testclient import TestClient

from langchain_core.messages import AIMessage, ToolMessage

from app.main import app
from app.schemas.responses import ChatResponse, ToolResult


# ─────────────────────────────────────────────────────────────────────────────
# Agent factory helper
# ─────────────────────────────────────────────────────────────────────────────

def make_agent_with_mock_graph(graph_return_value: dict):
    """
    Create an OrchestratorAgent with a mocked LangGraph compiled graph.
    The real registry is used (tools in mock mode).

    Args:
        graph_return_value: The dict that graph.invoke() will return,
                            representing the final graph state.
    """
    from app.orchestrator.agent import OrchestratorAgent
    from app.orchestrator.tool_registry import build_registry

    # Use __new__ to skip __init__ (avoids real ChatOpenAI initialisation)
    agent = OrchestratorAgent.__new__(OrchestratorAgent)
    agent._registry = build_registry()
    agent._lc_tools = agent._registry.to_langchain_tools()

    # Mock the LLM (needed for _inject_image_paths which doesn't call it, but
    # agent.run() accesses _graph — not _llm — so this is mostly a safety guard)
    agent._llm = MagicMock()

    # Mock the compiled graph
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = graph_return_value
    agent._graph = mock_graph

    return agent


# ─────────────────────────────────────────────────────────────────────────────
# OrchestratorAgent unit tests
# ─────────────────────────────────────────────────────────────────────────────

class TestOrchestratorAgent:

    def test_direct_text_response_no_tools(self):
        """
        If the LLM responds with plain text (no tool calls),
        the orchestrator should return that text immediately.
        """
        final_text = "Hello! How can I help you with satellite imagery?"
        ai_msg = AIMessage(content=final_text)

        agent = make_agent_with_mock_graph({
            "messages": [ai_msg],
            "tool_call_records": [],
            "artifacts": [],
            "error": None,
        })

        result = agent.run("Hello")
        assert isinstance(result, ChatResponse)
        assert final_text in result.answer
        assert len(result.tool_calls) == 0

    def test_analyze_image_tool_call_routing(self):
        """
        Simulate the graph executing analyze_image and returning a final answer.
        The orchestrator should extract the tool call record and final answer.
        """
        call_id = "call_test_001"
        tool_args = {"query": "What is visible?", "image": "/img/test.tif"}
        tool_result = ToolResult(
            tool="analyze_image",
            model="MBZUAI/EarthDial-4B-MS",
            mode="mock",
            answer="[MOCK — EarthDial-4B-MS] Test image analysis result.",
        )

        agent = make_agent_with_mock_graph({
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "analyze_image",
                        "args": tool_args,
                        "id": call_id,
                        "type": "tool_call",
                    }],
                ),
                ToolMessage(
                    content=json.dumps(tool_result.model_dump()),
                    tool_call_id=call_id,
                ),
                AIMessage(content="Based on the EarthDial analysis, the image shows mixed land cover."),
            ],
            "tool_call_records": [],
            "artifacts": [],
            "error": None,
        })

        result = agent.run(
            "What is visible in this satellite image?",
            image_path="/img/test.tif",
        )
        assert isinstance(result, ChatResponse)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].tool_name == "analyze_image"
        assert result.tool_calls[0].result.mode == "mock"
        assert len(result.answer) > 0

    def test_detect_change_tool_call_routing(self):
        """
        Simulate the graph executing detect_change.
        """
        call_id = "call_test_002"
        tool_args = {"query": "What changed between these images?"}
        tool_result = ToolResult(
            tool="detect_change",
            model="VisTA",
            mode="mock",
            answer="[MOCK — VisTA] Significant urban expansion in north-east.",
        )

        agent = make_agent_with_mock_graph({
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "detect_change",
                        "args": tool_args,
                        "id": call_id,
                        "type": "tool_call",
                    }],
                ),
                ToolMessage(
                    content=json.dumps(tool_result.model_dump()),
                    tool_call_id=call_id,
                ),
                AIMessage(content="The VisTA analysis reveals significant urban expansion."),
            ],
            "tool_call_records": [],
            "artifacts": [],
            "error": None,
        })

        result = agent.run(
            "Compare these two satellite images and identify changes.",
            image_path="/img/before.tif",
            image_path_t2="/img/after.tif",
        )
        assert isinstance(result, ChatResponse)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].tool_name == "detect_change"

    def test_analyze_sar_optical_tool_call_routing(self):
        """
        Simulate the graph executing analyze_sar_optical with LLM-selected models.
        """
        call_id = "call_test_003"
        tool_args = {"query": "Detect flood extent", "selected_models": "closp"}
        tool_result = ToolResult(
            tool="analyze_sar_optical",
            model="DarthReca/closp",
            mode="mock",
            answer="[MOCK — CLOSP] Flood inundation confirmed in eastern region.",
        )

        agent = make_agent_with_mock_graph({
            "messages": [
                AIMessage(
                    content="",
                    tool_calls=[{
                        "name": "analyze_sar_optical",
                        "args": tool_args,
                        "id": call_id,
                        "type": "tool_call",
                    }],
                ),
                ToolMessage(
                    content=json.dumps(tool_result.model_dump()),
                    tool_call_id=call_id,
                ),
                AIMessage(content="CLOSP analysis confirms flood inundation in the eastern region."),
            ],
            "tool_call_records": [],
            "artifacts": [],
            "error": None,
        })

        result = agent.run(
            "Analyze this SAR image alongside the optical image for flood detection.",
            sar_image_path="/img/sar.tif",
            image_path="/img/optical.tif",
        )
        assert isinstance(result, ChatResponse)
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].tool_name == "analyze_sar_optical"

    def test_graph_error_returns_error_response(self):
        """
        If the graph raises an exception, the orchestrator should return
        a ChatResponse with an error message, not re-raise.
        """
        from app.orchestrator.agent import OrchestratorAgent
        from app.orchestrator.tool_registry import build_registry

        agent = OrchestratorAgent.__new__(OrchestratorAgent)
        agent._registry = build_registry()
        agent._lc_tools = agent._registry.to_langchain_tools()
        agent._llm = MagicMock()
        mock_graph = MagicMock()
        mock_graph.invoke.side_effect = RuntimeError("Test graph error")
        agent._graph = mock_graph

        result = agent.run("Hello")
        assert isinstance(result, ChatResponse)
        assert result.error is not None
        assert "error" in result.answer.lower() or len(result.answer) > 0


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI endpoint tests (uses TestClient — no real network needed)
# ─────────────────────────────────────────────────────────────────────────────

class TestChatEndpoint:

    def test_health_endpoint(self):
        """Health check should always return 200 with registered_tools list."""
        with patch("app.orchestrator.agent.ChatOpenAI"):
            with TestClient(app) as client:
                response = client.get("/api/v1/health")
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "ok"
                assert "registered_tools" in data

    def test_chat_endpoint_returns_chat_response_schema(self):
        """POST /api/v1/chat must return a valid ChatResponse when agent succeeds."""
        mock_response = ChatResponse(
            answer="This is a mock satellite image analysis.",
            tool_calls=[],
            artifacts=[],
            model="mock-model",
            request_id="test-001",
        )

        with patch("app.orchestrator.agent.ChatOpenAI"):
            with TestClient(app) as client:
                # Patch the agent stored in app state after startup
                client.app.state.agent.run = MagicMock(return_value=mock_response)
                response = client.post(
                    "/api/v1/chat",
                    json={"message": "What is visible in this satellite image?"},
                )
                assert response.status_code == 200
                data = response.json()
                assert "answer" in data
                assert "tool_calls" in data
                assert "model" in data

    def test_chat_endpoint_validation_error(self):
        """Sending an invalid body (missing 'message') should return 422."""
        with patch("app.orchestrator.agent.ChatOpenAI"):
            with TestClient(app) as client:
                response = client.post("/api/v1/chat", json={})
                assert response.status_code == 422
