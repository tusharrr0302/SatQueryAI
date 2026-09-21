"""
app/services/llm_client.py
─────────────────────────────────────────────────────────────────────────────
LLM Client abstraction.

WHY THIS EXISTS:
  We don't want the orchestrator to directly import `openai` and hard-code
  the provider. This file wraps the OpenAI SDK and reads all configuration
  from environment variables.

  Because Groq, Together, vLLM, and Ollama all expose an OpenAI-compatible
  API, the SAME code works for all of them — just change LLM_BASE_URL
  and LLM_API_KEY in your .env.

WHAT THE ORCHESTRATOR USES:
  client = LLMClient()
  response = client.chat(messages, tools)

  The response is a standard openai ChatCompletion object, so the orchestrator
  can check response.choices[0].message.tool_calls to see if GPT-OSS
  wants to call a tool.

SWITCHING PROVIDERS:
  Groq:     LLM_BASE_URL=https://api.groq.com/openai/v1
  OpenAI:   LLM_BASE_URL=https://api.openai.com/v1
  Together: LLM_BASE_URL=https://api.together.xyz/v1
  vLLM:     LLM_BASE_URL=http://localhost:8001/v1
  Ollama:   LLM_BASE_URL=http://localhost:11434/v1
"""

from typing import Any
import openai
from loguru import logger
from app.config import settings


class LLMClient:
    """
    A thin wrapper around the OpenAI Python SDK that can target any
    OpenAI-compatible provider by changing environment variables.

    The orchestrator uses this class — it never imports openai directly.
    """

    def __init__(self) -> None:
        # Validate that an API key was provided
        if not settings.llm_api_key:
            logger.warning(
                "LLM_API_KEY is not set. The orchestrator will fail when "
                "attempting to call the LLM. Set LLM_API_KEY in your .env file."
            )

        # The openai client is configured with our provider's base_url.
        # This is how we support Groq, Together, vLLM, etc. with the same code.
        self._client = openai.OpenAI(
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )

        logger.info(
            f"LLMClient initialised | provider={settings.llm_provider} "
            f"| model={settings.llm_model} "
            f"| base_url={settings.llm_base_url}"
        )

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
    ) -> openai.types.chat.ChatCompletion:
        """
        Send a chat completion request to the LLM provider.

        Args:
            messages: Conversation history in OpenAI message format.
                      Each message is {"role": "...", "content": "..."}
            tools: Optional list of tool definitions in OpenAI function
                   calling format (from ToolRegistry.to_openai_tools()).
                   When provided, GPT-OSS can choose to call them.
            tool_choice: "auto" means GPT-OSS decides whether to call a tool.
                         "none" forces a plain text response.
                         {"type": "function", "function": {"name": "..."}}
                         forces a specific tool.

        Returns:
            OpenAI ChatCompletion response object.
            The orchestrator inspects:
              response.choices[0].message.content   → text response
              response.choices[0].message.tool_calls → tool call requests
        """
        logger.debug(
            f"LLMClient.chat | model={settings.llm_model} "
            f"| messages={len(messages)} "
            f"| tools={'yes' if tools else 'no'}"
        )

        # Build kwargs — only include 'tools' if actually provided.
        # Some providers error if you pass an empty tools list.
        kwargs: dict[str, Any] = {
            "model": settings.llm_model,
            "messages": messages,
            "max_tokens": settings.llm_max_tokens,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        try:
            response = self._client.chat.completions.create(**kwargs)
            logger.debug(
                f"LLMClient.chat response | "
                f"finish_reason={response.choices[0].finish_reason} "
                f"| tool_calls={'yes' if response.choices[0].message.tool_calls else 'no'}"
            )
            return response

        except openai.AuthenticationError as e:
            logger.error(f"LLM authentication failed — check LLM_API_KEY: {e}")
            raise
        except openai.RateLimitError as e:
            logger.error(f"LLM rate limit exceeded: {e}")
            raise
        except openai.APIConnectionError as e:
            logger.error(f"LLM connection failed — check LLM_BASE_URL: {e}")
            raise
        except openai.BadRequestError as e:
            logger.error(f"LLM bad request (model may not support tool calling): {e}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected LLM error: {e}")
            raise
