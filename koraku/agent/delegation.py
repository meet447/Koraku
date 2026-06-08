"""Composio sub-agent delegation mixin for the Koraku agent."""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any

from koraku.core.config import settings
from koraku.core.redact import redact_secrets
from koraku.core.models import SessionState
from koraku.agent.context_manager import ContextManager
from koraku.llm.catalog import resolve_effective_model, resolve_provider_id
from koraku.tools.registry import tools_for_execution_target
from koraku.integrations import composio as composio_runtime
from koraku.agent.composio_delegate_context import get_composio_delegate_context
from koraku.integrations.blaxel_runtime import resolve_blaxel_session_root
from koraku.agent.prompt_sections import format_runtime_context_section
from koraku.agent.budget import (
    TurnLimits,
    composio_max_rounds_for_goal,
    composio_wall_seconds_for_goal,
    composio_worker_sop_appendix,
    classify_composio_goal,
    tools_for_composio_worker,
)
from koraku.agent.agent_definition import AgentDefinition
from koraku.agent.task_delegate_context import get_task_delegate_context


_DELEGATION_TOOL_NAMES: frozenset[str] = frozenset({"Task", "ComposioRun"})


def _resolve_agent_definition(agents: dict[str, AgentDefinition], name: str) -> AgentDefinition | None:
    key = (name or "").strip()
    if not key:
        return None
    if key in agents:
        return agents[key]
    lower = key.lower()
    for k, defn in agents.items():
        if k.lower() == lower:
            return defn
    return None


def _tools_for_task_subagent(
    *,
    definition: AgentDefinition,
    execution_target: str,
    blaxel_sandbox_active: bool,
    allow_task: bool,
) -> list[Any]:
    from koraku.tools.registry import tools_for_execution_target

    pool = [
        t
        for t in tools_for_execution_target(execution_target, blaxel_sandbox_active=blaxel_sandbox_active)
        if t.name not in _DELEGATION_TOOL_NAMES or (allow_task and t.name == "Task")
    ]
    if definition.tools:
        allowed = {n.strip() for n in definition.tools if n.strip()}
        if allow_task:
            allowed.add("Task")
        return [t for t in pool if t.name in allowed]
    return list(pool)


def _subagent_final_assistant_text(session: SessionState) -> str:
    for msg in reversed(session.messages):
        if msg.role != "assistant":
            continue
        c = msg.content
        if isinstance(c, str):
            t = c.strip()
            if t:
                return t
        if isinstance(c, list):
            texts: list[str] = []
            for block in c:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(str(block.get("text") or ""))
            joined = "\n".join(texts).strip()
            if joined:
                return joined
    return "No assistant text was produced in the integration run."


def build_composio_subagent_system_prompt(
    workspace: str,
    toolkits: list[str],
    client_timezone: str | None = None,
    client_locale: str | None = None,
    execution_environment_note: str | None = None,
    *,
    cloud_tool_root: str | None = None,
    goal_class: str = "integration_full",
) -> str:
    """Narrow system prompt for a Composio-only scoped run."""
    ws = os.path.abspath(workspace)
    runtime = format_runtime_context_section(client_timezone, client_locale)
    env_extra = f"\n{execution_environment_note}\n" if execution_environment_note else ""
    ctr = ""
    if cloud_tool_root:
        ctr = f"\n- File tools use paths relative to `{cloud_tool_root.rstrip('/')}`.\n"
    tk = ", ".join(toolkits)
    return f"""You are Koraku's **integration worker** (scoped background agent).

## Task
- Composio toolkits in this run: **{tk}**.
- Fulfill the latest **user** message using those Composio tools plus workspace and web tools as needed.
- Do **not** claim inbox/calendar counts, 'no emails', or 'nothing found' until after you have run the relevant list/fetch tool and read the response.
- Before any send, post, or external write: confirm recipients, timing, and content from tool results.

{runtime}

## Workspace
- Root: `{ws}`{ctr}{env_extra}

## Reply
- Finish with a concise summary the main Koraku agent can relay: outcomes, errors, ids, times, or links.
- Do not mention ComposioRun, sub-agents, or internal architecture.
{composio_worker_sop_appendix(goal_class)}
"""


class SubagentDelegationMixin:
    async def _execute_composio_subagent(
        self,
        *,
        toolkits: list[str],
        goal: str,
        max_steps_override: int | None = None,
    ) -> str:
        ctx = get_composio_delegate_context()
        if ctx is None:
            return "Error: ComposioRun invoked without active delegate context."
        if not composio_runtime.is_configured():
            return "Error: Composio is not configured."
        if not goal.strip():
            return "Error: `goal` must be a non-empty string."

        comp_tools = await asyncio.to_thread(composio_runtime.build_dynamic_composio_tools_for_toolkits, toolkits)
        if not comp_tools:
            active = ", ".join(composio_runtime.active_toolkit_slugs()) or "(none)"
            return (
                "Error: No Composio tools loaded for those toolkits. "
                f"Each slug must be ACTIVE in Connections. Active now: {active}."
            )

        inner_registry_tok: Any = None
        try:
            inner_registry_tok = composio_runtime.push_composio_tool_registry(comp_tools)
        except Exception as e:
            return f"Error: could not register Composio tools: {redact_secrets(str(e))}"

        sub_session_id = f"{ctx.session.session_id}:composio"
        sub_session = SessionState(session_id=sub_session_id)
        sub_cm = ContextManager(
            max_messages=24,
            summarize_after=14,
            max_tool_result_chars=self.context_manager.max_tool_result_chars,
            compact_tool_rounds=self.context_manager.compact_tool_rounds,
        )

        base = [
            t
            for t in tools_for_execution_target(
                ctx.execution_target,
                blaxel_sandbox_active=ctx.blaxel_sandbox_active,
            )
            if t.name != "ComposioRun"
        ]
        goal_class = classify_composio_goal(goal)
        active_sub = tools_for_composio_worker(base, comp_tools, goal)
        eff_provider = resolve_provider_id(ctx.provider)
        effective_model = resolve_effective_model(ctx.model, provider_id=eff_provider)
        max_sub = composio_max_rounds_for_goal(goal, override=max_steps_override)
        sub_limits = TurnLimits(
            task_class=goal_class,
            max_rounds=max_sub,
            wall_seconds=composio_wall_seconds_for_goal(goal),
            started_monotonic=time.monotonic(),
        )

        session_root: str | None = None
        if ctx.cloud_sandbox is not None:
            try:
                override = (
                    (ctx.run_context.blaxel_session_root or "").strip()
                    if ctx.run_context
                    else None
                ) or None
                session_root = resolve_blaxel_session_root(
                    ctx.session.session_id,
                    settings,
                    override_root=override,
                )
            except Exception:
                session_root = None
        env_note: str | None = None
        if ctx.cloud_sandbox is not None and session_root:
            env_note = (
                f"- **Blaxel sandbox** (this chat): **Read**, **Write**, **Edit**, **Bash**, "
                f"**Glob**, **Grep** under `{session_root}`."
            )

        tk_seen: set[str] = set()
        for t in comp_tools:
            cats = t.categories or []
            if len(cats) > 1:
                tk_seen.add(str(cats[1]).upper())
        scoped_for_prompt = sorted(tk_seen)

        system_prompt = build_composio_subagent_system_prompt(
            ctx.workspace,
            scoped_for_prompt,
            client_timezone=ctx.client_timezone,
            client_locale=ctx.client_locale,
            execution_environment_note=env_note,
            cloud_tool_root=session_root if ctx.cloud_sandbox is not None else None,
            goal_class=goal_class,
        )
        sub_session.add_message("user", goal.strip())
        sub_session.step_count = 0

        def nested_emit(ev: dict[str, Any]) -> None:
            ctx.emit(
                {
                    **ev,
                    "subagent": {"composio": True, "toolkits": list(scoped_for_prompt)},
                }
            )

        nested_emit({"type": "agent.subagent", "data": {"phase": "composio_start", "toolkits": scoped_for_prompt}})
        last_reason: str | None = None
        try:
            async for ev in self._iterate_react_steps(
                session=sub_session,
                emit=nested_emit,
                active_tools=active_sub,
                system_prompt=system_prompt,
                working_memory=[],
                effective_model=effective_model,
                eff_provider=eff_provider,
                mode="composio_sub",
                limits=sub_limits,
                cancel_event=ctx.cancel_event,
                run_id=ctx.run_id,
                context_manager=sub_cm,
            ):
                if ev.get("type") == "agent.completed":
                    d = ev.get("data")
                    if isinstance(d, dict):
                        last_reason = str(d.get("reason") or "") or last_reason
        finally:
            composio_runtime.reset_composio_tool_registry(inner_registry_tok)

        nested_emit({"type": "agent.subagent", "data": {"phase": "composio_end", "toolkits": scoped_for_prompt}})
        out = _subagent_final_assistant_text(sub_session)
        if last_reason == "max_steps_reached":
            out += "\n\n(Integration worker stopped at max steps; retry with a narrower goal or higher max_steps.)"
        return out

    async def _execute_task_subagent(
        self,
        *,
        agent_name: str,
        prompt: str,
        max_steps_override: int | None = None,
    ) -> str:
        ctx = get_task_delegate_context()
        if ctx is None:
            return "Error: Task invoked without active delegate context."
        if not prompt.strip():
            return "Error: `prompt` must be a non-empty string."

        definition = _resolve_agent_definition(ctx.agents, agent_name)
        if definition is None:
            known = ", ".join(sorted(ctx.agents.keys())) or "(none)"
            return f"Error: Unknown subagent {agent_name!r}. Registered agents: {known}."

        max_depth = max(1, int(settings.subagent_max_depth))
        if ctx.depth >= max_depth:
            return (
                f"Error: Subagent nesting limit ({max_depth}) reached. "
                "Finish work in the current agent instead of spawning another Task."
            )

        sub_session_id = f"{ctx.session.session_id}:task:{agent_name.lower()}"
        sub_session = SessionState(session_id=sub_session_id)
        sub_cm = ContextManager(
            max_messages=24,
            summarize_after=14,
            max_tool_result_chars=self.context_manager.max_tool_result_chars,
            compact_tool_rounds=self.context_manager.compact_tool_rounds,
        )

        allow_nested_task = ctx.depth + 1 < max_depth
        active_sub = _tools_for_task_subagent(
            definition=definition,
            execution_target=ctx.execution_target,
            blaxel_sandbox_active=ctx.blaxel_sandbox_active,
            allow_task=allow_nested_task,
        )
        if not active_sub:
            return f"Error: Subagent {agent_name!r} has no available tools for this execution target."

        eff_provider = resolve_provider_id(definition.provider or ctx.provider)
        effective_model = resolve_effective_model(
            definition.model or ctx.model,
            provider_id=eff_provider,
        )
        max_sub = max_steps_override or definition.max_steps or int(settings.subagent_max_steps)
        sub_limits = TurnLimits(
            task_class="subagent",
            max_rounds=max(2, int(max_sub)),
            wall_seconds=float(settings.subagent_wall_seconds),
            started_monotonic=time.monotonic(),
        )

        session_root: str | None = None
        env_note: str | None = None
        if ctx.cloud_sandbox is not None:
            try:
                override = (
                    (ctx.run_context.blaxel_session_root or "").strip()
                    if ctx.run_context
                    else None
                ) or None
                session_root = resolve_blaxel_session_root(
                    ctx.session.session_id,
                    settings,
                    override_root=override,
                )
                env_note = (
                    f"- **Blaxel sandbox** (this chat): file tools under `{session_root}`."
                )
            except Exception:
                session_root = None

        runtime = format_runtime_context_section(ctx.client_timezone, ctx.client_locale)
        system_prompt = (
            f"{definition.prompt.rstrip()}\n\n"
            f"## Runtime\n{runtime}\n\n"
            f"## Workspace\nRoot: `{os.path.abspath(ctx.workspace)}`\n"
        )
        if env_note:
            system_prompt = f"{system_prompt}{env_note}\n"
        system_prompt += (
            "\n## Reply\n"
            "Finish with a concise summary the lead agent can relay. "
            "Do not mention Task, sub-agents, or internal architecture.\n"
        )

        sub_session.add_message("user", prompt.strip())
        sub_session.step_count = 0

        agent_key = agent_name.strip()
        sub_meta = {"task": True, "agent": agent_key}

        def nested_emit(ev: dict[str, Any]) -> None:
            ctx.emit({**ev, "subagent": dict(sub_meta)})

        nested_emit({"type": "agent.subagent", "data": {"phase": "task_start", "agent": agent_key}})
        last_reason: str | None = None
        try:
            async for ev in self._iterate_react_steps(
                session=sub_session,
                emit=nested_emit,
                active_tools=active_sub,
                system_prompt=system_prompt,
                working_memory=[],
                effective_model=effective_model,
                eff_provider=eff_provider,
                mode="task_sub",
                limits=sub_limits,
                cancel_event=ctx.cancel_event,
                run_id=ctx.run_id,
                context_manager=sub_cm,
            ):
                if ev.get("type") == "agent.completed":
                    d = ev.get("data")
                    if isinstance(d, dict):
                        last_reason = str(d.get("reason") or "") or last_reason
        finally:
            pass

        nested_emit({"type": "agent.subagent", "data": {"phase": "task_end", "agent": agent_key}})
        out = _subagent_final_assistant_text(sub_session)
        if last_reason == "max_steps_reached":
            out += "\n\n(Subagent stopped at max steps; retry with a narrower prompt or higher max_steps.)"
        return out
