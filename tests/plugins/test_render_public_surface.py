from __future__ import annotations

import ast
from pathlib import Path

RENDER_INIT = (
    Path(__file__).resolve().parents[2]
    / "apeiria"
    / "builtin_plugins"
    / "render"
    / "__init__.py"
)
MISSING_ALL_EXPORTS = "__all__ not found"


def test_render_public_surface_uses_canonical_helper_names() -> None:
    exported = _read_all_exports(RENDER_INIT)

    assert {"render_html", "render_template", "render_url", "render_markdown"} <= set(
        exported
    )
    assert {
        "html_to_pic",
        "template_to_pic",
        "url_to_pic",
        "markdown_to_pic",
    }.isdisjoint(exported)


def _read_all_exports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if not any(
                isinstance(target, ast.Name) and target.id == "__all__"
                for target in node.targets
            ):
                continue
            if not isinstance(node.value, ast.List):
                continue
            return [
                item.value
                for item in node.value.elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            ]
    raise AssertionError(MISSING_ALL_EXPORTS)
