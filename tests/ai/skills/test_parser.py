"""Tests for skill file parsing and runtime activation."""

from __future__ import annotations

import pytest

from apeiria.ai.skills.parser import (
    AISkillFileDefinition,
    SkillParseError,
    parse_skill_file,
)
from apeiria.ai.skills.runtime import AISkillRuntime

_VALID_SKILL = """---
name: test-skill
description: A test prompt skill for unit tests
version: 1
triggers:
  - keyword
entry_mode: prompt_only
---

# Test Skill

This is the body content of the skill.

## Section

More content here.
"""

_NO_FRONTMATTER = "Just some markdown without frontmatter."

_MISSING_NAME = """---
description: Missing required name field
version: 1
---

Body
"""

_MINIMAL = """---
name: minimal
description: A minimal skill
version: 1
---

Minimal body.
"""


class TestParseSkillFile:
    def test_parses_valid_skill(self) -> None:
        skill = parse_skill_file(_VALID_SKILL, file_path="test/SKILL.md")
        assert isinstance(skill, AISkillFileDefinition)
        assert skill.skill_name == "test-skill"
        assert skill.description == "A test prompt skill for unit tests"
        assert skill.entry_mode == "prompt_only"
        assert skill.version == 1
        assert len(skill.triggers) >= 1
        assert "This is the body content" in skill.body_markdown
        assert "## Section" in skill.body_markdown

    def test_parses_minimal_skill(self) -> None:
        skill = parse_skill_file(_MINIMAL, file_path="m/SKILL.md")
        assert skill.skill_name == "minimal"
        assert skill.version == 1
        assert skill.description == "A minimal skill"
        assert skill.entry_mode == "prompt_only"
        assert "Minimal body" in skill.body_markdown

    def test_rejects_no_frontmatter(self) -> None:
        with pytest.raises(SkillParseError):
            parse_skill_file(_NO_FRONTMATTER, file_path="bad.md")

    def test_rejects_missing_name(self) -> None:
        with pytest.raises(SkillParseError):
            parse_skill_file(_MISSING_NAME, file_path="missing_name.md")


class TestSkillRuntime:
    def test_register_and_activate_skills(self) -> None:
        rt = AISkillRuntime()
        a = parse_skill_file(_VALID_SKILL, file_path="a/SKILL.md")
        b = parse_skill_file(_MINIMAL, file_path="b/SKILL.md")
        rt.register_file_skills([a, b])
        assert rt.has_file_skills()

        activation = rt.activate_skill_explicit("test-skill")
        assert activation is not None
        assert activation.skill_name == "test-skill"
        assert "body content" in activation.body_markdown

        assert rt.activate_skill_explicit("minimal") is not None

    def test_activate_nonexistent_skill(self) -> None:
        rt = AISkillRuntime()
        assert rt.activate_skill_explicit("nope") is None
