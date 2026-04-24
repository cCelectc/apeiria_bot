"""Environment bootstrap phase for extension-path and plugin-config setup."""

from apeiria.environment.extension_project import (
    inject_plugin_site_packages,
    process_pending_plugin_module_uninstalls,
    process_pending_plugin_requirement_removals,
)
from apeiria.plugins.config_bootstrap import bootstrap_plugin_configs


def run_environment_phase() -> None:
    process_pending_plugin_requirement_removals()
    process_pending_plugin_module_uninstalls()
    inject_plugin_site_packages()
    # Plugin config bootstrap must run after extension site-packages are exposed,
    # otherwise plugins installed only in `.apeiria/extensions` cannot be scanned.
    bootstrap_plugin_configs()
