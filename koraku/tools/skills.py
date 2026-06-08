"""Discover modular Koraku skills from the workspace (.koraku/skills/*/SKILL.md)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_SLASH_RE = re.compile(r"^/([a-zA-Z0-9][a-zA-Z0-9_-]{0,63})(?:\s+(.*))?$", re.DOTALL)


@dataclass(frozen=True)
class SkillMeta:
    slug: str
    description: str
    path: str


@dataclass(frozen=True)
class SlashInvocation:
    slug: str
    user_message: str
    prompt_appendix: str


def skill_roots(workspace: str) -> Path:
    return Path(workspace).resolve() / ".koraku" / "skills"


def _skill_file(workspace: str, slug: str) -> Path | None:
    root = skill_roots(workspace)
    skill_dir = (root / slug).resolve()
    try:
        skill_dir.relative_to(root.resolve())
    except ValueError:
        return None
    skill_file = skill_dir / "SKILL.md"
    return skill_file if skill_file.is_file() else None


def _skill_description(body: str, slug: str) -> str:
    for line in body.splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        return text[:240]
    return f"Run the `{slug}` workspace skill."


def list_skills(workspace: str) -> list[SkillMeta]:
    root = skill_roots(workspace)
    if not root.is_dir():
        return []
    out: list[SkillMeta] = []
    for skill_dir in sorted(root.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            continue
        try:
            body = skill_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        slug = skill_dir.name
        out.append(
            SkillMeta(
                slug=slug,
                description=_skill_description(body, slug),
                path=str(skill_file),
            )
        )
    return out


def slash_commands_for_ui(workspace: str) -> list[dict[str, str]]:
    """Slash command metadata for SSE ``system/init`` and chat UIs."""
    return [
        {"name": skill.slug, "description": skill.description}
        for skill in list_skills(workspace)
    ]


def load_skill_body(workspace: str, slug: str, *, max_chars: int = 12_000) -> str | None:
    skill_file = _skill_file(workspace, slug)
    if skill_file is None:
        return None
    try:
        body = skill_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if len(body) > max_chars:
        body = body[:max_chars] + "\n\n[... skill file truncated ...]"
    return body


def parse_slash_command(message: str) -> tuple[str, str] | None:
    """Return ``(slug, remainder)`` when ``message`` is ``/slug`` or ``/slug args``."""
    text = (message or "").strip()
    if not text.startswith("/"):
        return None
    match = _SLASH_RE.match(text)
    if not match:
        return None
    slug = match.group(1).strip()
    remainder = (match.group(2) or "").strip()
    return slug, remainder


def resolve_slash_invocation(message: str, workspace: str) -> SlashInvocation | None:
    """Expand ``/skill-slug optional args`` into a user turn + skill prompt appendix."""
    parsed = parse_slash_command(message)
    if parsed is None:
        return None
    slug, remainder = parsed
    body = load_skill_body(workspace, slug)
    if body is None:
        return None
    user_message = remainder or f"Follow the `{slug}` skill instructions."
    appendix = (
        f"## Active skill: `{slug}`\n"
        f"The user invoked `/ {slug}` — treat the following SKILL.md as authoritative for this turn.\n\n"
        f"{body}\n"
    )
    return SlashInvocation(slug=slug, user_message=user_message, prompt_appendix=appendix)


def load_skill_catalog(workspace: str, max_total_chars: int = 14_000, per_skill_cap: int = 6_000) -> str:
    """Return markdown-ish text listing skills and trimmed SKILL.md bodies for the system prompt."""
    root = skill_roots(workspace)
    if not root.is_dir():
        return ""

    chunks: list[str] = []
    total = 0
    for skill_dir in sorted(root.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.is_file():
            continue
        try:
            body = skill_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        slug = skill_dir.name
        if len(body) > per_skill_cap:
            body = body[:per_skill_cap] + "\n\n[... skill file truncated for context ...]"
        block = f"### Skill: `{slug}`\n{body}\n"
        if total + len(block) > max_total_chars:
            chunks.append("\n[Additional skills omitted to stay within context budget.]\n")
            break
        chunks.append(block)
        total += len(block)

    if not chunks:
        return ""

    slugs = ", ".join(f"`/{s.slug}`" for s in list_skills(workspace))
    header = "## Loaded workspace skills\n"
    if slugs:
        header += f"Invoke directly in chat with slash commands: {slugs}.\n"
    return header + "".join(chunks)
