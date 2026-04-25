"""Agent Studio routing for Koraku daily-driver tasks.

This layer is deterministic on purpose: it gives every turn a structured operating
plan before the LLM starts deciding tool calls. Future versions can replace role
steps with independent subagent calls while keeping this event/schema stable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from src.workspace.artifacts import normalize_run_slug


@dataclass(frozen=True)
class StudioRole:
    name: str
    objective: str


@dataclass(frozen=True)
class StudioArtifact:
    path: str
    artifact_type: str
    purpose: str


@dataclass(frozen=True)
class StudioPlan:
    mode: str
    run_slug: str
    title: str
    reason: str
    roles: list[StudioRole] = field(default_factory=list)
    artifacts: list[StudioArtifact] = field(default_factory=list)
    approval_gates: list[str] = field(default_factory=list)
    suggested_todos: list[dict[str, str]] = field(default_factory=list)

    @property
    def enabled(self) -> bool:
        return self.mode == "studio"

    def to_event_payload(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "run_slug": self.run_slug,
            "title": self.title,
            "reason": self.reason,
            "roles": [r.__dict__ for r in self.roles],
            "artifacts": [a.__dict__ for a in self.artifacts],
            "approval_gates": list(self.approval_gates),
            "suggested_todos": list(self.suggested_todos),
        }


_RESEARCH_HINTS = (
    "research",
    "compare",
    "comparison",
    "investigate",
    "analyze",
    "analysis",
    "market",
    "competitor",
    "competitors",
    "vendor",
    "vendors",
    "best",
    "recommend",
    "decision",
    "report",
    "brief",
)
_WORKFLOW_HINTS = (
    "send",
    "email",
    "mail",
    "schedule",
    "calendar",
    "book",
    "create",
    "draft",
    "spreadsheet",
    "excel",
    "csv",
    "slides",
    "document",
    "workflow",
    "automation",
    "automate",
)
_APPROVAL_HINTS = (
    "send",
    "email",
    "mail",
    "book",
    "buy",
    "purchase",
    "post",
    "publish",
    "delete",
    "cancel",
    "schedule",
    "invite",
    "automation",
    "automate",
)


def _title_from_text(text: str, fallback: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", text.lower())[:7]
    if not words:
        return fallback
    return " ".join(w.capitalize() for w in words)


def _todo(id_: str, content: str, status: str = "pending") -> dict[str, str]:
    return {"id": id_, "content": content, "status": status}


def _needs_studio(text: str, *, has_images: bool, max_steps_override: int | None) -> tuple[bool, str]:
    t = text.lower()
    if max_steps_override is not None:
        return True, "automation or bounded background run"
    if has_images and len(t.split()) > 8:
        return True, "multimodal task with enough context to plan"
    if len(t.split()) > 45:
        return True, "multi-step prompt"
    if any(h in t for h in _RESEARCH_HINTS) and any(h in t for h in _WORKFLOW_HINTS):
        return True, "research plus workflow execution"
    if sum(1 for h in _RESEARCH_HINTS if h in t) >= 2:
        return True, "research/analysis task"
    if sum(1 for h in _WORKFLOW_HINTS if h in t) >= 2:
        return True, "workflow/document task"
    return False, "simple direct task"


def build_studio_plan(
    user_input: str,
    *,
    has_images: bool = False,
    max_steps_override: int | None = None,
) -> StudioPlan:
    """Create the deterministic studio plan for a user turn."""
    text = (user_input or "").strip()
    title = _title_from_text(text, "Koraku Task")
    slug = normalize_run_slug(title)
    enabled, reason = _needs_studio(text, has_images=has_images, max_steps_override=max_steps_override)
    if not enabled:
        return StudioPlan(
            mode="direct",
            run_slug=slug,
            title=title,
            reason=reason,
            roles=[StudioRole("Director", "Handle the user request directly with minimal ceremony.")],
            suggested_todos=[_todo("direct", "Complete the user's request directly", "in_progress")],
        )

    t = text.lower()
    roles = [
        StudioRole("Director", "Define the objective, constraints, deliverables, and approval gates."),
        StudioRole("Planner", "Create a short execution plan and identify durable artifacts."),
    ]
    artifacts = [
        StudioArtifact("plan.md", "plan", "Intent, assumptions, milestones, and approval gates."),
        StudioArtifact("action-log.md", "action_log", "Chronological log of important actions and decisions."),
    ]
    todos = [_todo("plan", "Create the task-room plan", "in_progress")]

    if any(h in t for h in _RESEARCH_HINTS):
        roles.extend(
            [
                StudioRole("Scout", "Collect source material, links, files, or integration context."),
                StudioRole("Analyst", "Extract claims, compare options, and build the evidence model."),
                StudioRole("Skeptic", "Challenge stale facts, weak evidence, and missing counterpoints."),
            ]
        )
        artifacts.extend(
            [
                StudioArtifact("sources.json", "sources", "Source ledger with relevance, claims, and confidence."),
                StudioArtifact("evidence-table.md", "evidence", "Comparison matrix, tradeoffs, risks, and recommendation support."),
                StudioArtifact("final-brief.md", "brief", "Polished answer or decision memo with citations."),
            ]
        )
        todos.extend(
            [
                _todo("scout", "Gather and record sources"),
                _todo("analyze", "Build evidence table and recommendation"),
                _todo("skeptic", "Check gaps and unsupported claims"),
            ]
        )

    if any(h in t for h in _WORKFLOW_HINTS):
        roles.append(StudioRole("Operator", "Draft or execute workflow actions after required approvals."))
        artifacts.append(StudioArtifact("workflow.md", "workflow", "Workflow steps, drafts, handoffs, and execution status."))
        todos.append(_todo("operate", "Draft or execute workflow steps"))
        if "email" in t or "mail" in t or "send" in t:
            artifacts.append(StudioArtifact("draft-email.md", "email_draft", "Email subject/body and recipient/action notes."))

    roles.append(StudioRole("Archivist", "Save reusable artifacts so the user can resume or automate the work later."))
    todos.append(_todo("archive", "Save final artifacts and summarize next actions"))

    approval_gates: list[str] = []
    if any(h in t for h in _APPROVAL_HINTS):
        approval_gates.append("Ask for explicit approval before irreversible external actions.")
    if "automation" in t or "automate" in t or max_steps_override is not None:
        approval_gates.append("Confirm trigger, schedule/event source, and connected apps before creating or activating automations.")

    return StudioPlan(
        mode="studio",
        run_slug=slug,
        title=title,
        reason=reason,
        roles=roles,
        artifacts=artifacts,
        approval_gates=approval_gates,
        suggested_todos=todos,
    )


def studio_system_section(plan: StudioPlan) -> str:
    """Prompt section injected into the current turn."""
    if not plan.enabled:
        return (
            "## Current turn operating mode\n"
            f"- Mode: direct\n- Reason: {plan.reason}\n"
            "- Keep the response/tool loop short unless the user asks for deeper work.\n"
        )

    role_lines = "\n".join(f"- {r.name}: {r.objective}" for r in plan.roles)
    artifact_lines = "\n".join(
        f"- `.koraku/runs/{plan.run_slug}/{a.path}` ({a.artifact_type}): {a.purpose}"
        for a in plan.artifacts
    )
    approval_lines = "\n".join(f"- {g}" for g in plan.approval_gates) or "- No special approval gate detected beyond normal safety."
    return f"""## Current turn Agent Studio plan
- Mode: studio
- Task room: `.koraku/runs/{plan.run_slug}/`
- Title: {plan.title}
- Reason: {plan.reason}

### Role routing
{role_lines}

### Expected artifacts
{artifact_lines}

### Approval gates
{approval_lines}

Start by using TodoWrite with these phases, then use ArtifactWrite for durable outputs as work becomes concrete.
"""
