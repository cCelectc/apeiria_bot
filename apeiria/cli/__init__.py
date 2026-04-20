"""CLI interface package."""

from apeiria.cli.commands.adapter import adapter
from apeiria.cli.commands.driver import driver
from apeiria.cli.commands.env import check, env, init, repair, run, status
from apeiria.cli.commands.plugin import plugin
from apeiria.cli.commands.resource import adapter as adapter_resource
from apeiria.cli.commands.resource import driver as driver_resource
from apeiria.cli.commands.resource import plugin as plugin_resource
from apeiria.cli.commands.webui import webui
from apeiria.cli.main import cli, main

__all__ = [
    "adapter",
    "adapter_resource",
    "check",
    "cli",
    "driver",
    "driver_resource",
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
