from __future__ import annotations

from pathlib import Path

from openharness.skills.loader import load_skill_registry


class SkillProvider:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def load_skill(self, name: str) -> tuple[str, bool]:
        try:
            registry = load_skill_registry(self.project_root)
            skill = registry.get(name)
            if skill is None:
                return "", False
            return skill.content, True
        except Exception:
            return "", False
