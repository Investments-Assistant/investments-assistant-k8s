"""Self-hosted OpenAI-compatible LLM client with tool routing.

The gateway expects a local OpenAI-compatible chat-completions endpoint such as
Ollama, vLLM, llama.cpp server, or another in-cluster model server. It does not
call a hosted LLM provider.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

import aiohttp

from src.agent.router import AgentRouter
from src.agent.tools import TOOL_DEFINITIONS
from src.auth import AuthContext, allowed_tool_definitions
from src.config import settings

logger = logging.getLogger(__name__)


def _openai_tools(auth_context: AuthContext | None) -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool["description"],
                "parameters": tool["input_schema"],
            },
        }
        for tool in allowed_tool_definitions(TOOL_DEFINITIONS, auth_context)
    ]


def _history_to_openai(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for message in messages:
        role = message.get("role")
        if role not in {"user", "assistant", "system", "tool"}:
            continue
        content = message.get("content", "")
        out.append({"role": role, "content": content if isinstance(content, str) else str(content)})
    return out


def _tool_input(tool_call: dict[str, Any]) -> tuple[str, dict]:
    function = tool_call.get("function") or {}
    name = function.get("name") or tool_call.get("name") or ""
    raw_arguments = function.get("arguments") or tool_call.get("arguments") or "{}"
    if isinstance(raw_arguments, dict):
        return name, raw_arguments
    try:
        parsed = json.loads(raw_arguments)
    except json.JSONDecodeError:
        parsed = {"_raw_arguments": raw_arguments}
    return name, parsed if isinstance(parsed, dict) else {}


class LocalLLMClient:
    """Calls a self-hosted OpenAI-compatible LLM and routes requested tools."""

    def __init__(self, router: AgentRouter) -> None:
        self._router = router
        self._timeout = aiohttp.ClientTimeout(total=settings.llm_request_timeout_seconds)

    async def stream_response(
        self,
        messages: list[dict[str, Any]],
        system: str,
        auth_context: AuthContext | None = None,
    ) -> AsyncGenerator[dict, None]:
        """
        Async generator yielding gateway-compatible events.

        Events:
          {"type": "text_delta",  "text": str}
          {"type": "tool_call",   "name": str, "input": dict, "id": str}
          {"type": "tool_result", "name": str, "result": str, "id": str}
          {"type": "done"}
          {"type": "error",       "message": str}
        """
        working_messages = [{"role": "system", "content": system}]
        working_messages.extend(_history_to_openai(messages))

        async with aiohttp.ClientSession(timeout=self._timeout) as session:
            for _ in range(settings.agent_max_tool_iterations):
                try:
                    message = await self._chat_completion(
                        session,
                        working_messages,
                        auth_context,
                    )
                except Exception as exc:
                    logger.exception("Local LLM request failed")
                    yield {"type": "error", "message": str(exc)}
                    return

                content = message.get("content") or ""
                if content:
                    yield {"type": "text_delta", "text": content}

                tool_calls = message.get("tool_calls") or []
                if not tool_calls:
                    yield {"type": "done"}
                    return

                working_messages.append(
                    {
                        "role": "assistant",
                        "content": content or None,
                        "tool_calls": tool_calls,
                    }
                )

                for tool_call in tool_calls:
                    tool_id = tool_call.get("id") or f"call_{uuid4().hex}"
                    name, tool_input = _tool_input(tool_call)
                    if not name:
                        result_str = json.dumps({"error": "Tool call missing function name"})
                    elif "_raw_arguments" in tool_input:
                        result_str = json.dumps(
                            {
                                "error": "Tool arguments were not valid JSON",
                                "arguments": tool_input["_raw_arguments"],
                            }
                        )
                    else:
                        yield {
                            "type": "tool_call",
                            "name": name,
                            "input": tool_input,
                            "id": tool_id,
                        }
                        result_str = await self._router.dispatch(
                            name,
                            tool_input,
                            auth_context=auth_context,
                        )

                    yield {
                        "type": "tool_result",
                        "name": name or "unknown",
                        "result": result_str,
                        "id": tool_id,
                    }
                    working_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_id,
                            "name": name or "unknown",
                            "content": result_str,
                        }
                    )

        yield {
            "type": "error",
            "message": "Maximum tool iterations reached before the model completed.",
        }

    async def _chat_completion(
        self,
        session: aiohttp.ClientSession,
        messages: list[dict[str, Any]],
        auth_context: AuthContext | None,
    ) -> dict[str, Any]:
        url = f"{settings.llm_base_url.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if settings.llm_api_key:
            headers["Authorization"] = f"Bearer {settings.llm_api_key}"

        payload = {
            "model": settings.llm_model_name,
            "messages": messages,
            "tools": _openai_tools(auth_context),
            "tool_choice": "auto",
            "temperature": settings.agent_temperature,
            "max_tokens": settings.agent_max_tokens,
            "stream": False,
        }
        async with session.post(url, json=payload, headers=headers) as response:
            text = await response.text()
            if response.status >= 400:
                raise RuntimeError(f"LLM server returned {response.status}: {text[:500]}")
            data = json.loads(text)

        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("LLM server response did not include choices")
        return choices[0].get("message") or {}
