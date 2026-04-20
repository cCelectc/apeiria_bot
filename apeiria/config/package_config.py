from __future__ import annotations

from typing import Any

from apeiria.plugins.package_ids import normalize_package_id


def normalize_string_list(
    value: object,
    *,
    ignore_literal_null: bool = False,
) -> list[str]:
    if not isinstance(value, list | tuple):
        return []

    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            continue
        normalized = item.strip()
        if not normalized:
            continue
        if ignore_literal_null and normalized.lower() in {"none", "null"}:
            continue
        result.append(normalized)
    return result


def normalize_package_item_map(value: object) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}

    result: dict[str, list[str]] = {}
    for package_name, items in value.items():
        if not isinstance(package_name, str) or not package_name.strip():
            continue
        normalized_items = sorted(set(normalize_string_list(items)))
        package_key = package_name.strip()
        if package_key and normalized_items:
            result[package_key] = normalized_items
    return result


def add_unique_sorted_item(items: list[str], item: str) -> bool:
    if item in items:
        return False
    items.append(item)
    items.sort()
    return True


def remove_item_from_config_packages(
    config: dict[str, Any],
    *,
    items_key: str,
    item: str,
) -> None:
    config[items_key] = [value for value in config[items_key] if value != item]
    for package_name in list(config["packages"]):
        config["packages"][package_name] = [
            value for value in config["packages"][package_name] if value != item
        ]
        if not config["packages"][package_name]:
            del config["packages"][package_name]


def bind_package_item(
    config: dict[str, Any],
    *,
    package_name: str,
    item: str,
) -> bool:
    package_key = package_name.strip()
    if not package_key:
        return False

    package_items = set(config["packages"].get(package_key, []))
    package_items.add(item)
    config["packages"][package_key] = sorted(package_items)
    return True


def get_package_bound_items(
    config: dict[str, Any],
    *,
    package_name: str,
) -> list[str]:
    package_key = package_name.strip()
    if not package_key:
        return []
    if package_key in config["packages"]:
        return list(config["packages"][package_key])

    normalized_package = normalize_package_id(package_key)
    if not normalized_package:
        return []

    matched_items: set[str] = set()
    for current_key, current_items in config["packages"].items():
        if normalize_package_id(current_key) == normalized_package:
            matched_items.update(current_items)
    return sorted(matched_items)


def unbind_package_item(
    config: dict[str, Any],
    *,
    package_name: str,
    items_key: str,
    item: str | None = None,
) -> bool:
    package_key = package_name.strip()
    if not package_key:
        return False

    matched_keys = (
        [package_key]
        if package_key in config["packages"]
        else [
            current_key
            for current_key in config["packages"]
            if normalize_package_id(current_key) == normalize_package_id(package_key)
        ]
    )
    if not matched_keys:
        return False

    if item is None:
        removed_items: list[str] = []
        for current_key in matched_keys:
            removed_items.extend(config["packages"].pop(current_key, []))
        for removed_item in removed_items:
            config[items_key] = [
                value for value in config[items_key] if value != removed_item
            ]
        return bool(removed_items)

    removed = False
    for current_key in matched_keys:
        package_items = config["packages"].get(current_key, [])
        if not package_items:
            continue
        next_items = [value for value in package_items if value != item]
        if len(next_items) == len(package_items):
            continue
        removed = True
        if next_items:
            config["packages"][current_key] = next_items
        else:
            del config["packages"][current_key]
    config[items_key] = [value for value in config[items_key] if value != item]
    return removed
