"""Koraku agent — one ReAct loop for every turn (Claude Code–style), with workspace skills + memory."""
import asyncio
import os
import re
from datetime import datetime
from typing import Any, AsyncIterator, Callable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.core.config import settings
from src.core.models import SessionState
from src.agent.context_manager import ContextManager
from src.llm.client import UnifiedLLMClient
from src.llm.catalog import bonsai_api_base, configured_provider_ids, is_provider_configured, resolve_effective_model
from src.tools.skills import load_skill_catalog
from src.tools.runtime import set_active_session
from src.tools.policy import tool_stdout_indicates_error
from src.agent.runtime_context import (
    AgentRunContext,
    resolve_agent_workspace,
    resolve_execution_target,
)
from src.tools.registry import tools_for_execution_target
from src.tools.tool_def import Tool
from src.integrations import composio as composio_runtime
from src.workspace.context import (
    load_agent_display_name,
    load_memory_snippet,
    load_soul_snippet,
    memory_path,
    soul_path,
)
from src.agent.blaxel_scope import blaxel_sandbox_scope
from src.workspace.agent_workspace import agent_workspace_scope


_CLIENT_META_SAFE = re.compile(r"^[A-Za-z0-9_./+\-]+$")
_CLIENT_LOCALE_SAFE = re.compile(r"^[A-Za-z0-9\-_]+$")


def _sanitize_client_meta(value: str | None, max_len: int = 120, pattern: re.Pattern[str] | None = None) -> str | None:
    if not value:
        return None
    s = value.strip()[:max_len]
    if not s or "\n" in s or "\r" in s:
        return None
    pat = pattern or _CLIENT_META_SAFE
    if not pat.match(s):
        return None
    return s


def format_runtime_context_section(
    client_timezone: str | None = None,
    client_locale: str | None = None,
) -> str:
    """Human-readable block for the system prompt (timezone-aware 'today', regional news, etc.)."""
    tz = _sanitize_client_meta(client_timezone, pattern=_CLIENT_META_SAFE)
    loc = _sanitize_client_meta(client_locale, max_len=40, pattern=_CLIENT_LOCALE_SAFE)
    utc_now = datetime.now(tz=ZoneInfo("UTC"))

    lines = [
        "## User runtime context (from the chat client)",
        f"- Authoritative UTC time on server: `{utc_now:%Y-%m-%d %H:%M:%S} UTC`",
    ]
    if tz:
        try:
            local = utc_now.astimezone(ZoneInfo(tz))
            lines.append(f"- User IANA timezone: `{tz}` → local time `{local:%Y-%m-%d %H:%M:%S %Z}`")
        except ZoneInfoNotFoundError:
            lines.append(f"- User timezone string was sent but is not a valid IANA zone: `{tz[:80]}` (ignore for clock math).")
    else:
        lines.append(
            "- No IANA timezone was provided. For 'today', 'this week', or local scheduling, infer from the "
            "user's wording or ask once; prefer **WebSearch** with explicit dates when recency matters."
        )
    if loc:
        lines.append(f"- Browser / OS locale: `{loc}` (use for number/date formatting and regional results when relevant).")
    lines.append(
        "- For **latest news** or time-sensitive facts: combine this clock context with **WebSearch** "
        "(include year or `prefer_recency_days` when appropriate); do not assume training cutoff is 'now'."
    )
    return "\n".join(lines) + "\n\n"


def _resolve_tool_from_active(tool_name: str, active_tools: list[Any]) -> Tool | None:
    for t in active_tools:
        if t.name == tool_name:
            return t
    return None


def build_user_message_blocks(
    user_input: str,
    image_parts: list[dict[str, str]],
) -> str | list[dict[str, Any]]:
    """Plain string when no images; otherwise Anthropic-shaped user blocks (images then text)."""
    if not image_parts:
        return user_input
    blocks: list[dict[str, Any]] = [
        {
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": p.get("media_type") or "image/png",
                "data": p.get("data") or "",
            },
        }
        for p in image_parts
    ]
    text = user_input.strip() or "The user attached image(s). Answer based on what you see."
    blocks.append({"type": "text", "text": text})
    return blocks


def _get_mode_and_budget(
    budget_text: str, max_steps_override: int | None
) -> tuple[str, int]:
    """Determine the operating mode and maximum steps for the agent turn."""
    if max_steps_override is not None:
        cap = max(1, min(int(max_steps_override), settings.research_max_steps))
        return "automation", cap
    return _step_budget(budget_text)


def _resolve_provider(provider: str | None) -> str:
    """Resolve the effective provider ID to use."""
    active = (settings.llm_provider or "custom_openai").strip().lower()
    eff_provider = (provider or "").strip().lower() or active
    if eff_provider not in ("anthropic", "fireworks", "custom_openai", "bonsai"):
        eff_provider = active
    if not is_provider_configured(eff_provider):
        ids = configured_provider_ids()
        eff_provider = ids[0] if ids else active
    if eff_provider not in ("anthropic", "fireworks", "custom_openai", "bonsai"):
        eff_provider = active
    return eff_provider


def _step_budget(user_input: str) -> tuple[str, int]:
    """UI hint + max agent steps; the model always gets tools — no separate 'chat-only' path."""
    text = user_input.lower()
    extended_markers = (
        "research", "compare", "comparison", " vs ", "versus", "investigate",
        "comprehensive", "thorough", "migrate", "refactor", "integrate",
        "codebase", "analyze the project", "full stack", "end to end",
        # Shopping / current-market web work (benefits from extra search+fetch steps)
        "price", "pricing", "cost ", "cheapest", "best deal", "where to buy",
        "in stock", "availability", "retailer",
    )
    words = len(text.split())
    if any(m in text for m in extended_markers) or words > 120:
        return "extended", settings.research_max_steps
    if words > 45:
        return "extended", min(settings.research_max_steps, settings.max_steps + 12)
    return "standard", settings.max_steps


def build_system_prompt(
    workspace: str,
    client_timezone: str | None = None,
    client_locale: str | None = None,
    execution_environment_note: str | None = None,
) -> str:
    ws = os.path.abspath(workspace)
    mem = load_memory_snippet(workspace)
    soul = load_soul_snippet(workspace)
    raw_display = load_agent_display_name(workspace)
    display_name = None
    if raw_display:
        safe = raw_display.replace("**", "").replace("\n", " ").strip()
        display_name = safe[:120] if safe else None
    skills = load_skill_catalog(workspace)

    memory_section = (
        f"## User memory (from `{memory_path(workspace)}`)\n{mem}\n"
        if mem
        else (
            f"## User memory\nPreferences and standing instructions live in `{memory_path(workspace)}` "
            "(create `.koraku/` when needed). Update that file when the user asks you to remember something durable.\n"
        )
    )

    soul_section = (
        f"## Persona / soul (from `{soul_path(workspace)}`)\n{soul}\n"
        if soul
        else (
            f"## Persona / soul\nOptional tone and roleplay layer: `{soul_path(workspace)}` (create when the user wants a fixed persona).\n"
        )
    )

    skills_section = (
        "## Workspace skills\n" + skills
        if skills
        else (
            "## Workspace skills\n"
            "No SKILL.md files found under `.koraku/skills/`. For specialized workflows, add "
            "`.koraku/skills/<slug>/SKILL.md` and follow those instructions before improvising.\n"
        )
    )

    composio_section = composio_runtime.composio_system_prompt_section()

    runtime = format_runtime_context_section(client_timezone, client_locale)

    name_line = ""
    if display_name:
        name_line = (
            f"- The user calls you **{display_name}**; use that name when a personal address fits. "
            "You are still Koraku — the same agent and capabilities underneath.\n"
        )

    env_extra = ""
    if execution_environment_note:
        env_extra = f"\n{execution_environment_note}\n"

    return f"""You are Koraku — an autonomous AI human emulator for real work in the user's workspace.

{runtime}## Identity
- You are decisive, tool-first, and completion-oriented. You do not roleplay hesitation.
{name_line}- You have filesystem, shell, search, and fetch tools today; future integrations (e.g. Gmail) will appear as additional tools when connected.

## Workspace
- Working directory: `{ws}`
- Treat paths relative to this directory unless the user specifies otherwise.
{env_extra}
{soul_section}

{memory_section}

{skills_section}

{composio_section}## Saved automations (Automations tab in the app)
- Users can save **automations** (scheduled cron jobs or event-style placeholders) that appear under **Automations** in the UI, with run history and **Run now**.
- Scheduled/manual runs use a **tighter step budget and wall-clock timeout** than interactive chat—keep automation instructions focused.
- Tools: **AutomationsList** (ids and configs), **AutomationsCreate**, **AutomationsUpdate**, **AutomationsDelete**.
- When the user describes a recurring task, digest, or “when X happens do Y”, interpret it and call **AutomationsCreate** with a clear `title`, full `natural_language_spec`, and either `trigger_mode: "scheduled"` plus valid IANA `timezone` and 5-field `cron_expression`, or `trigger_mode: "event"` plus `event_display` (e.g. `Gmail: New email`). Mention **Connections** if they need Gmail etc.
- Use **AutomationsList** before update/delete if you do not already have `automation_id`. After changes, remind them they can open **Automations** to run or pause.

## Core behavior
- Use tools whenever facts or artifacts depend on them. Prefer verifying over guessing.
- For multi-step tasks, maintain a visible plan with **TodoWrite** (merge=true) and update statuses as you go.
- Default to **creating or editing files** for deliverables (code, configs, research notes) instead of only chatting.
- Read before you edit; use **Edit** with exact `old_string` / `new_string` pairs.
- Use **WebSearch** then **WebPage** for time-sensitive or online-only information.
- After substantive code changes, run the project's tests, typecheck, or lint commands when available (**Bash**).
- Refuse destructive or illegal requests; never print secrets or API keys.

## Web research (match a strong human researcher)
- For prices, stock, shipping, laws, or anything time-bound: issue **several WebSearch calls in one turn** (parallel) with **different angles** — product + SKU + region + retailer names; add the **current year** when recency matters; use `site:example.com ...` when the user names a domain.
- Prefer **prefer_recency_days** (e.g. 365–700) on WebSearch for price/availability questions so results are not dominated by stale pages.
- After search, call **WebPage** on **1–2 canonical product or listing URLs** from different retailers or the official site **before** stating a price or “best pick.” Do not invent numbers from snippets alone.
- If WebSearch or WebPage returns an **error** in the tool result, retry with a narrower query, another retailer, or `include_html=true` when you only need links from a JS-heavy page — then say clearly if facts could not be verified.

## Autonomy
- Work through the full loop: plan → act with tools → verify → summarize what changed and where.
- If a tool errors, diagnose, adjust inputs, or try an alternative path before giving up.

## Parallelism
- When tool calls are independent, issue them in the same assistant turn so they can run in parallel.
"""


class Agent:
    """Anthropic-style agent loop: model chooses tools vs final text every turn."""

    def __init__(self) -> None:
        self._llm_by_provider: dict[str, UnifiedLLMClient] = {}
        self.context_manager = ContextManager(
            max_messages=28,
            summarize_after=14,
            max_tool_result_chars=max(4_000, int(settings.max_tool_result_chars)),
        )

    def _setup_active_tools(
        self,
        composio_registry_token: list[Any],
        emit: Callable[[dict[str, Any]], None],
        *,
        execution_target: str,
        blaxel_sandbox_active: bool,
    ) -> list[Any]:
        """Initialize tools and integrate Composio if configured."""
        active_tools = list(
            tools_for_execution_target(execution_target, blaxel_sandbox_active=blaxel_sandbox_active)
        )
        if composio_runtime.is_configured():
            try:
                comp = composio_runtime.build_dynamic_composio_tools()
                composio_registry_token[0] = composio_runtime.push_composio_tool_registry(comp)
                active_tools = active_tools + comp
            except Exception as e:
                emit({"type": "agent.warning", "data": {"composio": f"Could not load Composio tools: {e}"}})
        return active_tools

    def _llm(self, provider_id: str) -> UnifiedLLMClient:
        pid = provider_id.strip().lower()
        if pid == "bonsai":
            if "bonsai" not in self._llm_by_provider:
                self._llm_by_provider["bonsai"] = UnifiedLLMClient(
                    provider_override="custom_openai",
                    custom_base_url=bonsai_api_base(),
                )
            return self._llm_by_provider["bonsai"]
        if pid not in self._llm_by_provider:
            self._llm_by_provider[pid] = UnifiedLLMClient(provider_override=pid)
        return self._llm_by_provider[pid]

    async def run(
        self,
        user_input: str,
        session: SessionState,
        emit: Callable[[dict[str, Any]], None],
        workspace: str | None = None,
        model: str | None = None,
        provider: str | None = None,
        client_timezone: str | None = None,
        client_locale: str | None = None,
        image_parts: list[dict[str, str]] | None = None,
        max_steps_override: int | None = None,
        run_context: AgentRunContext | None = None,
        cloud_sandbox: Any | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        composio_registry_token: list[Any] = [None]
        try:
            async for row in self._run_agent_turn(
                user_input,
                session,
                emit,
                workspace,
                model,
                provider,
                client_timezone,
                client_locale,
                image_parts,
                composio_registry_token,
                max_steps_override=max_steps_override,
                run_context=run_context,
                cloud_sandbox=cloud_sandbox,
            ):
                yield row
        finally:
            composio_runtime.reset_composio_tool_registry(composio_registry_token[0])

    async def _run_agent_turn(
        self,
        user_input: str,
        session: SessionState,
        emit: Callable[[dict[str, Any]], None],
        workspace: str | None,
        model: str | None,
        provider: str | None,
        client_timezone: str | None,
        client_locale: str | None,
        image_parts: list[dict[str, str]] | None,
        composio_registry_token: list[Any],
        max_steps_override: int | None = None,
        run_context: AgentRunContext | None = None,
        cloud_sandbox: Any | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        ws = resolve_agent_workspace(workspace, run_context)
        execution_target = resolve_execution_target(run_context)
        blaxel_active = cloud_sandbox is not None
        env_note: str | None = None
        if cloud_sandbox is not None:
            try:
                sname = cloud_sandbox.metadata.name
            except Exception:
                sname = "sandbox"
            wd = settings.blaxel_sandbox_workdir
            env_note = (
                f"- **Blaxel sandbox `{sname}`**: **Read**, **Write**, **Edit**, **Bash**, **Glob**, and **Grep** "
                f"run inside this isolated VM. Prefer paths relative to `{wd}`."
            )
        with agent_workspace_scope(ws), blaxel_sandbox_scope(cloud_sandbox):
            composio_runtime.configure_workspace_cache(ws)
            eff_provider = _resolve_provider(provider)
            effective_model = resolve_effective_model(model, provider_id=eff_provider)
            imgs = list(image_parts or [])
            budget_text = user_input.strip() or ("[images]" if imgs else "")
            mode, max_steps = _get_mode_and_budget(budget_text, max_steps_override)

            mode_event = {
                "type": "agent.mode",
                "data": {
                    "mode": mode,
                    "max_steps": max_steps,
                    "model": effective_model,
                    "provider": eff_provider,
                    "session_id": session.session_id,
                    "execution_target": execution_target,
                    "blaxel_sandbox": blaxel_active,
                },
            }
            emit(mode_event)
            yield mode_event

            active_tools = self._setup_active_tools(
                composio_registry_token,
                emit,
                execution_target=execution_target,
                blaxel_sandbox_active=blaxel_active,
            )
            tool_names = [t.name for t in active_tools]
            tools_event = {"type": "agent.tools", "data": {"tools": tool_names, "count": len(tool_names)}}
            emit(tools_event)
            yield tools_event

            user_turn = build_user_message_blocks(user_input, imgs)
            session.add_message("user", user_turn)
            session.step_count = 0
            system_prompt = build_system_prompt(
                ws,
                client_timezone=client_timezone,
                client_locale=client_locale,
                execution_environment_note=env_note,
            )
            working_memory: list[dict[str, Any]] = []

            while session.step_count < max_steps:
                session.step_count += 1

                context_messages = self.context_manager.process_messages(session.messages)
                token_estimate = self.context_manager.estimate_tokens(context_messages)
                ctx_event = {
                    "type": "agent.context",
                    "data": {"messages": len(context_messages), "estimated_tokens": token_estimate},
                }
                emit(ctx_event)
                yield ctx_event

                assistant_content: list[dict[str, Any]] = []
                tool_uses: list[dict[str, Any]] = []

                async for event in self._llm(eff_provider).stream(
                    messages=context_messages,
                    tool_schemas=active_tools,
                    system_prompt=system_prompt,
                    model=effective_model,
                ):
                    wrapped = {"type": "stream_event", "event": event}
                    emit(wrapped)
                    yield wrapped

                    if event["type"] == "assistant_message":
                        assistant_content = event["message"]["content"]

                for block in assistant_content:
                    if block.get("type") == "tool_use":
                        tool_uses.append(block)

                if not tool_uses:
                    session.add_message("assistant", assistant_content, model=effective_model, stop_reason="end_turn")
                    done = {
                        "type": "agent.completed",
                        "data": {
                            "reason": "end_turn",
                            "steps": session.step_count,
                            "mode": mode,
                            "provider": eff_provider,
                            "model": effective_model,
                        },
                    }
                    emit(done)
                    yield done
                    return

                session.add_message("assistant", assistant_content, model=effective_model, stop_reason="tool_use")

                set_active_session(session)
                try:
                    tool_results = await self._execute_tools_parallel(tool_uses, emit, active_tools)
                finally:
                    set_active_session(None)

                for tr in tool_results:
                    result_event = {
                        "type": "user",
                        "message": {"role": "user", "content": [tr]},
                    }
                    emit(result_event)
                    yield result_event

                session.add_message("user", tool_results)

                self._update_memory(working_memory, tool_results)
                if working_memory:
                    mem_ev = {"type": "agent.memory", "data": {"findings": len(working_memory)}}
                    emit(mem_ev)
                    yield mem_ev

            done = {
                "type": "agent.completed",
                "data": {
                    "reason": "max_steps_reached",
                    "steps": session.step_count,
                    "mode": mode,
                    "provider": eff_provider,
                    "model": effective_model,
                },
            }
            emit(done)
            yield done

    def _update_memory(self, memory: list[dict[str, Any]], tool_results: list[dict[str, Any]]) -> None:
        for tr in tool_results:
            content = tr.get("content", "")
            if tr.get("is_error"):
                memory.append({"type": "error", "summary": str(content)[:100]})
            elif isinstance(content, str):
                if content.startswith("[") and "url" in content:
                    memory.append({"type": "results", "summary": f"Found {content.count('url')} sources"})
                elif len(content) > 200:
                    memory.append({"type": "content", "summary": f"Retrieved {len(content)} chars"})

    async def _execute_tools_parallel(
        self,
        tool_uses: list[dict[str, Any]],
        emit: Callable[[dict[str, Any]], None],
        active_tools: list[Any],
    ) -> list[dict[str, Any]]:
        for tool_use in tool_uses:
            exec_event = {
                "type": "tool_execution",
                "data": {
                    "tool": tool_use["name"],
                    "input": tool_use["input"],
                    "id": tool_use["id"],
                    "mode": "parallel" if len(tool_uses) > 1 else "sequential",
                },
            }
            emit(exec_event)

        if len(tool_uses) == 1:
            return [await self._execute_single_tool(tool_uses[0], active_tools)]

        async def run_one(tu: dict[str, Any]) -> dict[str, Any]:
            return await self._execute_single_tool(tu, active_tools)

        results = await asyncio.gather(*[run_one(tu) for tu in tool_uses], return_exceptions=True)
        processed: list[dict[str, Any]] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed.append({
                    "type": "tool_result", "tool_use_id": tool_uses[i]["id"],
                    "content": f"Error: {result}", "is_error": True,
                })
            else:
                processed.append(result)
        return processed

    async def _execute_single_tool(
        self,
        tool_use: dict[str, Any],
        active_tools: list[Any],
        max_retries: int = 2,
    ) -> dict[str, Any]:
        tool_name = tool_use["name"]
        tool_input = tool_use["input"]
        tool_id = tool_use["id"]

        tool = _resolve_tool_from_active(tool_name, active_tools)
        if tool is None:
            return {
                "type": "tool_result", "tool_use_id": tool_id,
                "content": f"Error: Tool '{tool_name}' not found.", "is_error": True,
            }

        last_error = ""
        for attempt in range(max_retries + 1):
            try:
                result_text = await tool.run(**tool_input)
                is_error = tool_stdout_indicates_error(result_text, tool_name=tool_name)
                if not is_error:
                    return {"type": "tool_result", "tool_use_id": tool_id, "content": result_text, "is_error": False}
                last_error = result_text
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))
            except Exception as e:
                last_error = str(e)
                if attempt < max_retries:
                    await asyncio.sleep(0.5 * (attempt + 1))

        return {
            "type": "tool_result", "tool_use_id": tool_id,
            "content": f"{last_error} (failed after {max_retries + 1} attempts)", "is_error": True,
        }
