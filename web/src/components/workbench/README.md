# Workbench Components

This directory owns the authenticated management workbench layer. Feature views
should compose these primitives before adding page-local layout.

## Boundaries

- `PageScaffold.vue` owns route title, context, page actions, alerts, and page
  spacing.
- `ResourceWorkbench.vue` owns resource summary, filters, actions, loading, and
  empty-state structure.
- `SettingsWorkbench.vue` owns grouped configuration section structure.
- `ActionCluster.vue` owns repeatable action grouping for primary, secondary,
  text, and destructive commands. Keep one primary command visible and move
  secondary commands into the `overflow` slot when the toolbar would crowd.
- `FilterBar.vue` owns search fields, select filters, presets, active filter
  summaries, reset/query actions, popup overflow filters, and mobile stacking.
- `SplitPane.vue`, `SelectableList.vue`, and `SelectableListItem.vue` own
  sidebar/detail management layouts and active/disabled/warning list states.
- `DetailPanel.vue` and `DenseList.vue` own selected-resource metadata,
  warnings, operational records, and dense row separators.
- `DataTablePanel.vue` owns framed dense data/table regions.
- `MetricStrip.vue`, `StatusBadge.vue`, `EmptyState.vue`, `TaskDialog.vue`, and
  `LogPanel.vue` own common operational state and feedback.
- `PopupPanel.vue` owns dialog-sized complex editors and dense detail panels
  that should not stay permanently inline.

## Visual Contract

Workbench components use the theme palette and `app.css` tokens for neutral
surfaces, one primary accent, semantic status colors, 1px separators, compact
radius, focus rings, and restrained elevation. Feature views should not recreate
toolbars, filter grids, split panes, selectable lists, task log dialogs, or dense
timeline rows with page-local styling unless the behavior is specific to that
domain.

Dialogs, forms, task feedback, data panels, and log panels should preserve the
existing route/API behavior while standardizing action placement, loading,
empty, warning, error, and success states through these primitives.

## Layout Rules

- A management page may use one primary tab-like layer. Secondary choices should
  use segmented controls, selects, side lists, menus, dialogs, or drawers.
- Keep persistent page chrome concise. Do not pass decorative subtitles to
  `PageScaffold` or repeated resource panels; keep helper text near the task.
- Keep primary search and primary actions reachable inline. Move secondary
  filters, presets, and bulk actions into `FilterBar` overflow or
  `ActionCluster` overflow when medium-width layouts would compress controls.
- Workbench pages with persistent sidebars, log streams, chat panels, or dense
  operational lists should opt into `PageScaffold fullHeight`. The page then
  stays fixed to the browser viewport on desktop, while the selected panel,
  list, log body, or message body owns vertical scrolling.
- Long configuration editors, raw payload previews, task logs, and dense details
  should use `PopupPanel`, `TaskDialog`, or another explicit Vuetify popup
  surface when inline display makes the route harder to scan.
- Use shared shape tiers from `app.css` rather than route-local `rounded` props
  or arbitrary radius literals. Use circular affordances only for icon/avatar
  semantics.
- The established blue theme palette is the baseline. Workbench changes may
  refine spacing, density, surfaces, elevation, and shape, but not the theme hue
  direction.

## Route Compatibility

Authenticated routes preserved by the workbench migration:

- `/dashboard`
- `/core`
- `/core/adapters/store`
- `/ai`
- `/plugins/config`
- `/plugins/store`
- `/permissions`
- `/logs`
- `/logs/history`
- `/chat`
- `/accounts`

## Inspection Set

Representative desktop and mobile checks should cover:

- `/dashboard`
- `/plugins/config`
- `/plugins/store`
- `/core`
- `/core/adapters/store`
- `/ai`
- `/permissions`
- `/logs`
- `/logs/history`
- `/chat`
- `/accounts`
