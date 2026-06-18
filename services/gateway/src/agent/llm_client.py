"""Self-hosted OpenAI-compatible LLM client with tool routing.

The gateway expects a local OpenAI-compatible chat-completions endpoint such as
Ollama, vLLM, llama.cpp server, or another in-cluster model server. It does not
call a hosted LLM provider.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

import aiohttp

from src.agent.router import AgentRouter
from src.agent.tools import TOOL_DEFINITIONS
from src.auth import AuthContext, allowed_tool_definitions
from src.config import settings

logger = logging.getLogger(__name__)


def _latest_user_message(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content", "")
            return content if isinstance(content, str) else str(content)
    return ""


def _direct_tool_intent(user_message: str) -> tuple[str, dict] | None:
    normalized = re.sub(r"\s+", " ", user_message.strip().lower())
    if not normalized:
        return None

    if "market overview" in normalized or "market snapshot" in normalized:
        return "get_market_overview", {}

    mode_match = re.search(
        r"\b(?:switch|set|change)\b.*\b(?:trading\s+mode|mode)\b.*\b(auto|recommend)\b",
        normalized,
    )
    if mode_match:
        return "set_trading_mode", {"mode": mode_match.group(1)}

    return None


def _looks_like_tool_call_example(role: str | None, content: str) -> bool:
    if role != "assistant":
        return False
    normalized = content.lower()
    return (
        "json function calls" in normalized
        or "function calls with their proper arguments" in normalized
        or ('{"name"' in content and '"parameters"' in content)
    )


def _format_number(value: Any) -> str:
    if not isinstance(value, int | float):
        return "n/a"
    if abs(value) >= 1000:
        return f"{value:,.2f}"
    return f"{value:.2f}"


def _format_market_overview(result_str: str) -> str:
    try:
        data = json.loads(result_str)
    except json.JSONDecodeError:
        return "I fetched the market overview, but the market-data response was not valid JSON."

    if data.get("error"):
        return (
            "I could not fetch a live market overview. "
            f"market-data returned: {data['error']} "
            "Source: get_market_overview."
        )

    markets = data.get("markets")
    if not isinstance(markets, dict) or not markets:
        return "I fetched the market overview, but the response did not include market rows."

    lines = ["Market overview right now, from `get_market_overview`:"]
    for name, info in markets.items():
        if not isinstance(info, dict):
            continue
        if info.get("error"):
            lines.append(f"- {name}: unavailable ({info['error']})")
            continue
        symbol = info.get("symbol")
        price = _format_number(info.get("price"))
        change = info.get("change_pct")
        change_text = f"{change:+.2f}%" if isinstance(change, int | float) else "n/a"
        suffix = f" ({symbol})" if symbol else ""
        lines.append(f"- {name}{suffix}: {price}, {change_text}")

    lines.append("Informational only; not financial advice.")
    return "\n".join(lines)


def _format_direct_tool_response(tool_name: str, result_str: str) -> str:
    if tool_name == "get_market_overview":
        return _format_market_overview(result_str)

    if tool_name == "set_trading_mode":
        try:
            data = json.loads(result_str)
        except json.JSONDecodeError:
            return "Trading mode update returned a malformed response."
        if data.get("error"):
            return f"I could not update trading mode: {data['error']}"
        return data.get("message") or f"Trading mode is now {data.get('trading_mode', 'updated')}."

    return ""


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
        content = content if isinstance(content, str) else str(content)
        if _looks_like_tool_call_example(role, content):
            continue
        out.append({"role": role, "content": content})
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

        direct_intent = _direct_tool_intent(_latest_user_message(messages))
        if direct_intent:
            tool_name, tool_input = direct_intent
            tool_id = f"call_{uuid4().hex}"
            yield {
                "type": "tool_call",
                "name": tool_name,
                "input": tool_input,
                "id": tool_id,
            }
            result_str = await self._router.dispatch(
                tool_name,
                tool_input,
                auth_context=auth_context,
            )
            yield {
                "type": "tool_result",
                "name": tool_name,
                "result": result_str,
                "id": tool_id,
            }
            summary = _format_direct_tool_response(tool_name, result_str)
            if summary:
                yield {"type": "text_delta", "text": summary}
            yield {"type": "done"}
            return

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
