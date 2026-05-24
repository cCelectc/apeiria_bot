# Builtin Plugin Publishing Audit

This audit adapts NoneBot plugin publishing requirements to Apeiria bundled
plugins. Builtins are not standalone store packages, so install instructions
describe bundled usage and dependencies may be declared by the project package.

## Checklist

- Loadable by NoneBot without required local secrets or manual runtime state.
- Top-level `PluginMetadata` includes name, description, usage, homepage, type,
  config when configurable, and supported-adapter intent.
- Cross-plugin dependencies are declared with `require()` before dependent
  imports or adapter inheritance, and Apeiria `required_plugins` matches runtime
  dependencies used by plugin management surfaces.
- README covers introduction, bundled installation/enabling, configuration,
  usage or developer/API surface, permissions or platform limits, and notes.
- Local plugin data/cache/config/log files use `nonebot-plugin-localstore`.
- Async matcher, request, service, and provider paths avoid obvious blocking
  network/process calls; small local reads/writes are noted where present.

## Matrix

| Plugin | Metadata | Dependencies | Adapter claim | README | Storage / async review | Action |
|:---|:---|:---|:---|:---|:---|:---|
| `apeiria.builtin_plugins.admin` | OK: application metadata, no config model | OK: `nonebot_plugin_alconna`, `nonebot_plugin_apscheduler` declared with `require()` and `required_plugins` | OK: inherits Alconna support | OK | No plugin-owned local files found; command handlers use project services | None |
| `apeiria.builtin_plugins.ai` | OK: application metadata, no config model | OK: `nonebot_plugin_alconna` declared with `require()` and `required_plugins` | OK: inherits Alconna support for status command | No dedicated README because this builtin is a single-file runtime shell; metadata is sufficient for current help/UI surface | No plugin-owned local files found; runtime work is async application calls | None |
| `apeiria.builtin_plugins.contact_approval` | OK: application metadata and config model | Fixed: added `nonebot_plugin_localstore` `require()` and `required_plugins` | OK: load-neutral metadata; README documents OneBot v11 practical support | Fixed: normalized sections and documented install/config/platform/storage/failure behavior | Fixed: default ticket file now resolves through localstore; provider calls are async `call_api` | Code/docs updated |
| `apeiria.builtin_plugins.contact_owner` | OK: application metadata and config model | OK: no cross-plugin dependency | OK: load-neutral metadata; README documents OneBot v11 QQ target support | OK | No plugin-owned local files found; provider uses async platform API boundary | None |
| `apeiria.builtin_plugins.help` | OK: application metadata and config model | OK: `nonebot_plugin_alconna`, `nonebot_plugin_localstore`, and `apeiria.builtin_plugins.render` declared before dependent submodule import | OK: inherits Alconna support | OK | Uses localstore for custom templates and disk cache; local image/template/cache file reads are bounded local operations | None |
| `apeiria.builtin_plugins.qq_tools` | OK: application metadata, no config model | OK: no cross-plugin dependency | OK: load-neutral metadata; README documents OneBot v11 QQ provider scope | OK | No plugin-owned local files found; provider uses async platform API boundary | None |
| `apeiria.builtin_plugins.render` | OK: library metadata and config model | OK: no cross-plugin dependency | OK: basic-abstraction library with `supported_adapters=None` | OK | No plugin-owned persistent files; Playwright work is async service work | None |
| `apeiria.builtin_plugins.repeater` | OK: application metadata and config model | OK: no cross-plugin dependency | OK: basic-abstraction matcher with configurable platform filter | OK | In-memory state only; no plugin-owned local files found | None |
| `apeiria.builtin_plugins.self_revoke` | OK: application metadata and config model | OK: no cross-plugin dependency | OK: load-neutral metadata; README documents practical supported adapters and fail-closed behavior | OK | No plugin-owned local files found; provider calls are async platform API boundaries | None |
| `apeiria.builtin_plugins.web_ui` | OK: application metadata and config model | OK: `nonebot_plugin_localstore` declared with `require()` and `required_plugins` | OK: server-side management plugin with no adapter dependency | OK | Uses localstore for access log path; FastAPI/static serving remains framework-managed | None |

## Notes

- Provider-backed plugins intentionally keep `supported_adapters=None` because
  they load without adapter-specific imports and select support at runtime.
  README files carry the practical platform support boundary.
- `contact_approval` is the only audit finding that required code changes: its
  persisted approval tickets previously used a project `data/` path directly.
- No structural metadata, dependency, or README tests were added for this audit.
