"""Per-session orchestrator: manages conversation history and drives the local LLM."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Any

from src.agent.llm_client import LocalLLMClient
from src.agent.prompts import SYSTEM_PROMPT
from src.agent.router import get_router
from src.auth import AuthContext, authorization_prompt
from src.config import settings

logger = logging.getLogger(__name__)


class Orchestrator:
    """Stateful orchestrator for one chat session."""

    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.history: list[dict[str, Any]] = []
        self._client = LocalLLMClient(router=get_router())

    def _system(self, auth_context: AuthContext | None) -> str:
        # Read trading_mode at call time so it reflects any runtime changes
        return SYSTEM_PROMPT.format(
            trading_mode=settings.trading_mode,
            auto_max_trade_usd=settings.auto_max_trade_usd,
            auto_daily_loss_limit_usd=settings.auto_daily_loss_limit_usd,
        ) + authorization_prompt(auth_context)

    def _trimmed(self) -> list[dict]:
        return self.history[-settings.agent_max_context_messages :]

    async def chat(
        self,
        user_message: str,
        auth_context: AuthContext | None = None,
    ) -> AsyncGenerator[dict, None]:
        """Stream agent response events for a user message."""
        self.history.append({"role": "user", "content": user_message})
        full_text = ""

        async for event in self._client.stream_response(
            messages=self._trimmed(),
            system=self._system(auth_context),
            auth_context=auth_context,
        ):
            if event["type"] == "text_delta":
                full_text += event["text"]
            yield event

        if full_text:
            self.history.append({"role": "assistant", "content": full_text})

        await self._persist(user_message, full_text)

    async def load_history(self) -> None:
        """Restore conversation history from DB for a returning session."""
        try:
            from sqlalchemy import select

            from src.db.database import async_session
            from src.db.models import ChatMessage

            async with async_session() as session:
                result = await session.execute(
                    select(ChatMessage)
                    .where(ChatMessage.session_id == self.session_id)
                    .order_by(ChatMessage.created_at)
                    .limit(settings.agent_max_context_messages)
                )
                msgs = result.scalars().all()
                self.history = [
                    {"role": m.role, "content": m.content}
                    for m in msgs
                    if m.role in ("user", "assistant")
                ]
        except Exception as exc:
            logger.warning("Failed to load history: %s", exc)

    async def _persist(self, user_msg: str, assistant_msg: str) -> None:
        try:
            from src.db.database import async_session
            from src.db.models import ChatMessage

            async with async_session() as session:
                session.add(ChatMessage(session_id=self.session_id, role="user", content=user_msg))
                if assistant_msg:
                    session.add(
                        ChatMessage(
                            session_id=self.session_id, role="assistant", content=assistant_msg
                        )
                    )
                await session.commit()
        except Exception as exc:
            logger.warning("Failed to persist chat messages: %s", exc)


# ── Global session registry ──────────────────────────────────────────────────

_sessions: dict[str, Orchestrator] = {}


def get_or_create_session(session_id: str) -> Orchestrator:
    if session_id not in _sessions:
        _sessions[session_id] = Orchestrator(session_id)
    return _sessions[session_id]
