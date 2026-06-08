"""Embeddable Koraku SDK facade for in-process agent runs."""
from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any

from koraku.agent import Agent
from koraku.agent.agent_definition import AgentDefinition
from koraku.agent.hooks import AgentHooks
from koraku.agent.pending_interactions import respond_to_interaction
from koraku.agent.permissions import PermissionMode
from koraku.agent.runtime_context import AgentRunContext, ExecutionTarget
from koraku.core.config import Settings, configure_sdk, use_settings
from koraku.core.models import SessionState
from koraku.core.sdk_settings import SdkSettings
from koraku.tools.tool_def import Tool

__all__ = ["AgentDefinition", "Koraku", "KorakuConfig"]


@dataclass
class KorakuConfig:
    """Embeddable configuration for in-process Koraku agents (SDK / local-first)."""

    llm_provider: str = "fireworks"
    fireworks_api_key: str = ""
    fireworks_model: str = "accounts/fireworks/models/kimi-k2p6"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    llm_openai_compat_ids: str = ""
    max_steps: int = 15
    max_tokens: int = 4096
    temperature: float = 0.5
    workspace: str | None = None
    execution_target: ExecutionTarget = "local"
    memory_backend: str = "filesystem"
    composio_api_key: str = ""
    composio_subagent_mode: bool = True
    enable_bash: bool = True
    enable_web_search: bool = True
    enable_file_ops: bool = True
    permission_mode: PermissionMode = "default"
    enable_ask_user: bool = True
    ask_user_timeout_seconds: float = 600.0
    hooks: AgentHooks | None = None
    agents: dict[str, AgentDefinition] = field(default_factory=dict)
    extra_tools: tuple[Tool, ...] = field(default_factory=tuple)

    def to_sdk_settings(self) -> SdkSettings:
        return SdkSettings(
            llm_provider=self.llm_provider,
            fireworks_api_key=self.fireworks_api_key,
            fireworks_model=self.fireworks_model,
            anthropic_api_key=self.anthropic_api_key,
            anthropic_model=self.anthropic_model,
            llm_openai_compat_ids=self.llm_openai_compat_ids,
            max_steps=self.max_steps,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            default_execution_target=self.execution_target,
            memory_backend=self.memory_backend,
            composio_api_key=self.composio_api_key,
            composio_subagent_mode=self.composio_subagent_mode,
            enable_bash=self.enable_bash,
            enable_web_search=self.enable_web_search,
            enable_file_ops=self.enable_file_ops,
            permission_mode=self.permission_mode,
            enable_ask_user=self.enable_ask_user,
            ask_user_timeout_seconds=self.ask_user_timeout_seconds,
        )

    def to_settings(self) -> Settings:
        """Merged settings view (SDK layer only unless Cloud was bootstrapped)."""
        from koraku.core.config import Settings as MergedSettings

        return MergedSettings(self.to_sdk_settings())


class Koraku:
    """In-process embeddable Koraku agent.

    Example::

        from koraku import Koraku, KorakuConfig

        agent = Koraku(KorakuConfig(fireworks_api_key="...", llm_provider="fireworks"))
        async for event in agent.stream("Summarize this repo"):
            print(event)
    """

    def __init__(
        self,
        config: KorakuConfig | SdkSettings | Settings | None = None,
        *,
        tools: list[Tool] | None = None,
    ) -> None:
        from koraku.core.config import Settings as MergedSettings

        if isinstance(config, SdkSettings):
            self._settings: Settings = MergedSettings(config)
        elif isinstance(config, Settings):
            self._settings = config
        elif config is not None:
            self._settings = config.to_settings()
        else:
            self._settings = MergedSettings(SdkSettings())
        extra = tuple(tools or ()) + (
            config.extra_tools if isinstance(config, KorakuConfig) else ()
        )
        self._tools = extra
        self._workspace = config.workspace if isinstance(config, KorakuConfig) else None
        self._agents = dict(config.agents) if isinstance(config, KorakuConfig) and config.agents else {}

    @property
    def settings(self) -> Settings:
        return self._settings

    def configure_process(self) -> None:
        """Apply this instance's SDK settings as the process-wide default."""
        configure_sdk(self._settings.sdk)

    def _agent(self) -> Agent:
        return Agent()

    async def stream(
        self,
        message: str,
        *,
        session: SessionState | None = None,
        session_id: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        workspace: str | None = None,
        execution_target: ExecutionTarget | None = None,
        cancel_event: asyncio.Event | None = None,
        permission_mode: PermissionMode | None = None,
        hooks: AgentHooks | None = None,
        agents: dict[str, AgentDefinition] | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run one agent turn and yield raw agent events (same shapes as the HTTP API internals)."""
        sid = session_id or str(uuid.uuid4())
        state = session or SessionState(session_id=sid)
        ws = workspace or self._workspace
        target: ExecutionTarget = execution_target or self._settings.default_execution_target  # type: ignore[assignment]
        eff_permission = permission_mode or self._settings.permission_mode  # type: ignore[assignment]
        eff_hooks = hooks
        run_context = AgentRunContext(
            workspace_root=ws,
            execution_target=target,
            extra_tools=self._tools,
            permission_mode=eff_permission,
            hooks=eff_hooks,
            ask_user_timeout_seconds=float(self._settings.ask_user_timeout_seconds),
            agents=dict(agents) if agents is not None else dict(self._agents),
        )

        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        def _emit(ev: dict[str, Any]) -> None:
            try:
                queue.put_nowait(ev)
            except asyncio.QueueFull:
                pass

        async def _run() -> None:
            try:
                with use_settings(self._settings):
                    agent = self._agent()
                    async for event in agent.run(
                        message,
                        state,
                        _emit,
                        workspace=ws,
                        model=model,
                        provider=provider,
                        run_context=run_context,
                        cancel_event=cancel_event,
                    ):
                        await queue.put(event)
            finally:
                await queue.put(None)

        task = asyncio.create_task(_run())
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item
        await task

    @staticmethod
    def respond_to_interaction(interaction_id: str, body: dict[str, Any]) -> bool:
        """Answer a pending AskUser question or approve/deny a sensitive tool (in-process)."""
        return respond_to_interaction(interaction_id, body)

    async def run(
        self,
        message: str,
        *,
        on_event: Callable[[dict[str, Any]], None] | None = None,
        **kwargs: Any,
    ) -> SessionState:
        """Run one turn and return the updated session (optional event callback)."""
        sid = kwargs.pop("session_id", None) or str(uuid.uuid4())
        state = kwargs.pop("session", None) or SessionState(session_id=sid)

        async for event in self.stream(message, session=state, session_id=sid, **kwargs):
            if on_event is not None:
                on_event(event)
        return state
