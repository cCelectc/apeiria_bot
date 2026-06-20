"""CLI interface package."""

from apeiria.cli.commands.env import check, env, init, repair, run, status
from apeiria.cli.commands.plugin import plugin
from apeiria.cli.commands.resource import plugin as plugin_resource
from apeiria.cli.commands.webui import webui
from apeiria.cli.main import cli, main

__all__ = [
    "check",
    "cli",
    "env",
    "init",
    "main",
    "plugin",
    "plugin_resource",
    "repair",
    "run",
    "status",
    "webui",
]
