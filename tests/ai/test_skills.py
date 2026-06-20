from __future__ import annotations

from apeiria.ai.skills.catalog import _skill_catalog, get_skill_body, get_skill_names


def setup_function() -> None:
    _skill_catalog.clear()


def test_get_skill_body() -> None:
    _skill_catalog["test"] = {
        "description": "A test skill",
        "body": "Full body content",
    }
    assert get_skill_body("test") == "Full body content"
    assert get_skill_body("nonexistent") is None


def test_get_skill_names() -> None:
    _skill_catalog["a"] = {"description": "Skill A", "body": "..."}
    _skill_catalog["b"] = {"description": "Skill B", "body": "..."}
    names = get_skill_names()
    assert len(names) == 2  # noqa: PLR2004
    assert ("a", "Skill A") in names
    assert ("b", "Skill B") in names


def test_empty_catalog() -> None:
    assert get_skill_names() == []
    assert get_skill_body("anything") is None


def test_load_skills_from_directory(tmp_path: object) -> None:
    from pathlib import Path

    from apeiria.ai.skills.catalog import load_skills

    skill_dir = Path(str(tmp_path)) / "skills"
    skill_dir.mkdir()
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(
        "---\nname: my_skill\ndescription: Test skill\n---\nSkill body here",
        encoding="utf-8",
    )
    load_skills([skill_dir])
    assert get_skill_body("my_skill") == "Skill body here"
    names = get_skill_names()
    assert ("my_skill", "Test skill") in names
