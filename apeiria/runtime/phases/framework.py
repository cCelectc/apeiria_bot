"""Framework bootstrap phase for core plugin and hook loading."""

from apeiria._framework_loader import load_framework


def run_framework_phase() -> None:
    load_framework()
