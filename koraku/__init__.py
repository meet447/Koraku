"""Koraku — embeddable ReAct agent SDK and self-hostable assistant."""

from koraku.agent import Agent, AgentRunContext, ExecutionTarget
from koraku.core.config import Settings, configure, configure_sdk, get_settings, get_sdk_settings, use_settings
from koraku.core.message_text import message_text
from koraku.core.sdk_settings import SdkSettings
from koraku.core.auth import AuthResult, auth_error_detail, verify_request_auth
from koraku.core.models import AgentMessage, SessionState
from koraku.llm import UnifiedLLMClient
from koraku.llm.dx import OpenAICompatProvider, list_provider_infos, list_providers, register_openai_compat_provider
from koraku.sdk_events import (
    EventType,
    KorakuEvent,
    collect_assistant_text,
    collect_stream_events_text,
    collect_stream_text,
    is_completed,
    parse_event,
)
from koraku.sdk import Koraku, KorakuConfig
from koraku.sdk_interactions import answer_question, approve_tool
from koraku.sdk_session import KorakuSession, KorakuSessionOptions
from koraku.sdk_types import (
    ActionData,
    ApprovalData,
    CompletedData,
    ErrorData,
    ExecutionTargets,
    LlmStreamEvent,
    PermissionModes,
    ProviderInfo,
    Question,
    QuestionData,
    QuestionOption,
    SubagentData,
)
from koraku.agent.agent_definition import AgentDefinition
from koraku.tools import Tool, get_tool, get_tool_schemas

__all__ = [
    "ActionData",
    "Agent",
    "AgentDefinition",
    "AgentMessage",
    "AgentRunContext",
    "ApprovalData",
    "AuthResult",
    "AVAILABLE_TOOLS",
    "CompletedData",
    "ErrorData",
    "EventType",
    "ExecutionTarget",
    "ExecutionTargets",
    "Koraku",
    "KorakuConfig",
    "KorakuEvent",
    "KorakuSession",
    "KorakuSessionOptions",
    "LlmStreamEvent",
    "OpenAICompatProvider",
    "PermissionModes",
    "ProviderInfo",
    "Question",
    "QuestionData",
    "QuestionOption",
    "SessionState",
    "Settings",
    "SubagentData",
    "Tool",
    "UnifiedLLMClient",
    "SdkSettings",
    "answer_question",
    "approve_tool",
    "auth_error_detail",
    "collect_assistant_text",
    "collect_stream_events_text",
    "collect_stream_text",
    "configure",
    "configure_sdk",
    "get_settings",
    "get_sdk_settings",
    "get_tool",
    "get_tool_schemas",
    "is_completed",
    "list_provider_infos",
    "list_providers",
    "message_text",
    "parse_event",
    "register_openai_compat_provider",
    "use_settings",
    "verify_request_auth",
]

__version__ = "0.2.0"


def __getattr__(name: str):
    if name == "AVAILABLE_TOOLS":
        from koraku.tools.registry import available_tools

        return available_tools()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
